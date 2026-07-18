import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger("transactions_performance")


class EscrowTransactionService:
    """
    Enhanced service for handling escrow transaction status updates
    with proper validation, error handling, and business logic separation
    """

    # Define valid status transitions as class constants
    VALID_TRANSITIONS = {
        "BUYER": {
            "initiated": ["cancelled"],
            "payment_received": ["disputed"],
            "shipped": ["delivered", "disputed"],
            "delivered": ["inspection", "disputed"],
            "inspection": ["completed", "disputed"],
            "disputed": [],
            "completed": [],
            "funds_released": [],
            "refunded": [],
            "cancelled": [],
        },
        "SELLER": {
            "initiated": ["payment_received", "cancelled"],
            "payment_received": ["shipped", "disputed"],
            "shipped": ["disputed"],
            "delivered": ["disputed"],
            "inspection": ["disputed"],
            "disputed": [],
            "completed": ["funds_released"],
            "funds_released": [],
            "refunded": [],
            "cancelled": [],
        },
    }

    # Status that require additional data
    STATUSES_REQUIRING_TRACKING = ["shipped"]
    STATUSES_WITH_TIME_LIMITS = ["inspection"]

    @classmethod
    def is_status_change_allowed(
        cls, transaction, new_status: str, user
    ) -> tuple[bool, str]:
        """
        Enhanced validation that returns both result and reason

        Returns:
            tuple: (is_allowed: bool, reason: str)
        """
        # System override (e.g. webhook or Celery task)
        if user is None:
            return True, "System override"

        # Staff can perform any transition
        if getattr(user, "is_staff", False):
            return True, "Staff override"

        # Check if user is participant in transaction
        is_buyer = user == transaction.buyer
        is_seller = user == transaction.seller

        if not (is_buyer or is_seller):
            return False, "User is not a participant in this transaction"

        # Determine user type
        user_type = "BUYER" if is_buyer else "SELLER"

        # Check if current status exists in transitions
        if transaction.status not in cls.VALID_TRANSITIONS[user_type]:
            return (
                False,
                f"No transitions available from current status {transaction.status}",
            )

        # Check if new status is allowed
        allowed_statuses = cls.VALID_TRANSITIONS[user_type][transaction.status]
        if new_status not in allowed_statuses:
            return (
                False,
                f"Cannot transition from {transaction.status} to {new_status} as {user_type.lower()}",
            )
        # Check if product is allow for inspection
        if new_status == "inspection":
            is_allowed_inspection = transaction.product.requires_inspection
            if not is_allowed_inspection:
                return (
                    False,
                    f"Inspection was NOT allow for this  product {transaction.product.title}",
                )

        return True, "Transition allowed"

    @classmethod
    def validate_status_requirements(
        cls, transaction, new_status: str, **kwargs
    ) -> tuple[bool, str]:
        """
        Validate that required data is provided for specific status changes

        Returns:
            tuple: (is_valid: bool, reason: str)
        """
        # Check if shipping info is required
        if new_status in cls.STATUSES_REQUIRING_TRACKING:
            if not kwargs.get("tracking_number"):
                return (
                    False,
                    f"Tracking number is required when updating status to '{new_status}'",
                )
            if not kwargs.get("shipping_carrier"):
                return (
                    False,
                    f"Shipping carrier is required when updating status to '{new_status}'",
                )

        # Add other validations as needed
        if new_status == "delivered" and not kwargs.get("delivery_confirmation"):
            # You might want delivery confirmation for some cases
            pass

        return True, "Validation passed"

    @staticmethod
    @transaction.atomic
    def _update_escrow_transaction_status(
        escrow_transaction,
        new_status: str,
        user=None,
        notes: str = "",
        tracking_number: Optional[str] = None,
        shipping_carrier: Optional[str] = None,
        **kwargs,
    ):
        """
        Enhanced transaction status update with comprehensive validation

        Args:
            escrow_transaction: The escrow transaction to update
            status: The new status
            user: The user performing the action
            notes: Additional notes about the status change
            tracking_number: Optional tracking number for shipping
            shipping_carrier: Optional shipping carrier name
            **kwargs: Additional parameters for future extensibility

        Returns:
            The updated escrow transaction

        Raises:
            ValidationError: If the status change is not allowed or invalid
        """
        try:
            # 1. Validate permissions
            is_allowed, permission_reason = (
                EscrowTransactionService.is_status_change_allowed(
                    escrow_transaction, new_status, user
                )
            )

            if not is_allowed:
                raise ValidationError(f"Permission denied: {permission_reason}")

            # 2. Validate requirements for this status
            is_valid, validation_reason = (
                EscrowTransactionService.validate_status_requirements(
                    escrow_transaction,
                    new_status,
                    tracking_number=tracking_number,
                    shipping_carrier=shipping_carrier,
                    **kwargs,
                )
            )
            if not is_valid:
                raise ValidationError(f"Validation failed: {validation_reason}")

            # 3. Store previous status for history
            previous_status = escrow_transaction.status

            # 4. Update the transaction
            escrow_transaction.status = new_status

            # 5. Handle status-specific logic
            EscrowTransactionService._handle_status_specific_logic(
                escrow_transaction, new_status, tracking_number, shipping_carrier
            )

            # 6. Save the transaction
            escrow_transaction.save()

            # 7. Create transaction history
            EscrowTransactionService._create_transaction_history(
                escrow_transaction, previous_status, new_status, notes, user
            )

            # 8. Handle post-update actions (notifications, etc.)
            EscrowTransactionService._handle_post_update_actions(
                escrow_transaction, previous_status, new_status, user, **kwargs
            )

            logger.info(
                f"Transaction {escrow_transaction.id} status updated from "
                f"{previous_status} to {new_status} by user {user.id if user else 'system'}"
            )

            return escrow_transaction

        except Exception as e:
            logger.error(
                f"Failed to update transaction {escrow_transaction.id} status to {new_status}: {str(e)}"
            )
            raise

    @staticmethod
    def _handle_status_specific_logic(
        escrow_transaction, status, tracking_number, shipping_carrier
    ):
        """Handle logic specific to certain status changes"""
        from apps.transactions.models import FundHold, SellerBalanceLedger
        from apps.transactions.services.ledger_service import SellerBalanceService

        # Update tracking info if provided
        if tracking_number:
            escrow_transaction.tracking_number = tracking_number
        if shipping_carrier:
            escrow_transaction.shipping_carrier = shipping_carrier

        # Set inspection end date when status is set to 'inspection'
        if status == "inspection":
            escrow_transaction.inspection_end_date = timezone.now() + timedelta(
                days=escrow_transaction.inspection_period_days
            )

        # Set completion timestamp
        if status == "completed":
            escrow_transaction.status_changed_at = timezone.now()

        # Set fund release timestamp
        if status == "funds_released":
            escrow_transaction.funds_released_at = timezone.now()

        # --- Holds and Ledger Integrations ---
        if status == "payment_received":
            # 1. Create standard transaction hold when payment received
            FundHold.objects.create(
                transaction=escrow_transaction,
                seller=escrow_transaction.seller,
                amount=escrow_transaction.total_amount,
                hold_type=FundHold.HOLD_TYPE_TRANSACTION,
                status=FundHold.STATUS_ACTIVE,
                reason=f"Standard hold for order #{escrow_transaction.id}",
            )

        elif status in ["completed", "funds_released"]:
            # 2. Release standard transaction holds and dispute holds
            active_holds = FundHold.objects.filter(
                transaction=escrow_transaction,
                status=FundHold.STATUS_ACTIVE,
                hold_type__in=[FundHold.HOLD_TYPE_TRANSACTION, FundHold.HOLD_TYPE_DISPUTE],
            )
            for hold in active_holds:
                hold.status = FundHold.STATUS_RELEASED
                hold.released_at = timezone.now()
                hold.save()

            # 3. Credit seller ledger if not already done for this transaction
            already_credited = SellerBalanceLedger.objects.filter(
                transaction=escrow_transaction,
                entry_type=SellerBalanceLedger.ENTRY_SALE_CREDIT,
            ).exists()

            if not already_credited:
                total_amount_dec = Decimal(str(escrow_transaction.total_amount))
                # Credit the sale amount
                SellerBalanceService.record_entry(
                    seller=escrow_transaction.seller,
                    amount=total_amount_dec,
                    entry_type=SellerBalanceLedger.ENTRY_SALE_CREDIT,
                    transaction_obj=escrow_transaction,
                    description=f"Credit for completed transaction #{escrow_transaction.id}",
                )

                # Debit the platform fee (default to 5% or setting)
                fee_percentage = Decimal(str(getattr(settings, "MARKETPLACE_FEE_PERCENTAGE", 0.05)))
                fee_amount = (total_amount_dec * fee_percentage).quantize(Decimal("0.01"))
                if fee_amount > 0:
                    SellerBalanceService.record_entry(
                        seller=escrow_transaction.seller,
                        amount=-fee_amount,
                        entry_type=SellerBalanceLedger.ENTRY_PLATFORM_FEE,
                        transaction_obj=escrow_transaction,
                        description=f"Platform fee ({fee_percentage * 100}%) for transaction #{escrow_transaction.id}",
                    )

        elif status == "disputed":
            # 4. Transition active transaction holds to dispute holds
            active_transaction_holds = FundHold.objects.filter(
                transaction=escrow_transaction,
                status=FundHold.STATUS_ACTIVE,
                hold_type=FundHold.HOLD_TYPE_TRANSACTION,
            )
            for hold in active_transaction_holds:
                hold.hold_type = FundHold.HOLD_TYPE_DISPUTE
                hold.reason = f"Frozen due to active dispute on order #{escrow_transaction.id}"
                hold.save()

        elif status in ["refunded", "cancelled"]:
            # 5. Void active holds
            active_holds = FundHold.objects.filter(
                transaction=escrow_transaction,
                status=FundHold.STATUS_ACTIVE,
            )
            for hold in active_holds:
                hold.status = FundHold.STATUS_VOIDED
                hold.released_at = timezone.now()
                hold.save()

    @classmethod
    @transaction.atomic
    def register_late_chargeback(cls, transaction_id: int, reason: str = ""):
        """
        Record a post-release card chargeback or dispute.
        Debits the seller's ledger balance and creates a dispute record.
        """
        from apps.transactions.models import EscrowTransaction, SellerBalanceLedger
        from apps.transactions.services.ledger_service import SellerBalanceService
        from apps.disputes.models import Dispute, DisputeStatus, DisputeReason

        escrow_transaction = EscrowTransaction.objects.get(id=transaction_id)
        
        # 1. Debit the seller ledger to claw back the funds
        SellerBalanceService.record_entry(
            seller=escrow_transaction.seller,
            amount=-Decimal(str(escrow_transaction.total_amount)),
            entry_type=SellerBalanceLedger.ENTRY_CHARGEBACK_DEBIT,
            transaction_obj=escrow_transaction,
            description=f"Late chargeback debit for transaction #{escrow_transaction.id}. Reason: {reason}",
        )

        # 2. Open a dispute of type chargeback_review if not exists
        dispute, created = Dispute.objects.get_or_create(
            transaction=escrow_transaction,
            defaults={
                "opened_by": escrow_transaction.buyer,
                "reason": DisputeReason.OTHER,
                "description": f"Late chargeback filed: {reason}",
                "status": DisputeStatus.OPENED,
            }
        )
        if not created:
            dispute.status = DisputeStatus.OPENED
            dispute.description += f" | Additional chargeback: {reason}"
            dispute.save()

        # Update transaction status to disputed to track in the system
        escrow_transaction.status = EscrowTransaction.STATUS_DISPUTED
        escrow_transaction.save()

        return dispute

    @staticmethod
    def _create_transaction_history(
        escrow_transaction, previous_status, new_status, notes, user
    ):
        """Create a transaction history record"""
        from apps.transactions.models import (
            TransactionHistory,
        )  # Avoid circular imports

        if not previous_status != new_status:
            return Response(
                {
                    "message": f"Status is already in: {new_status}",
                    "status_code": status.HTTP_400_BAD_REQUEST,
                }
            )
        TransactionHistory.objects.create(
            transaction=escrow_transaction,
            new_status=new_status,
            previous_status=previous_status,
            notes=notes,
            created_by=user,
        )

    @staticmethod
    def _handle_post_update_actions(
        escrow_transaction, previous_status, new_status, user, **kwargs
    ):
        """Handle actions that should happen after status update"""
        from apps.notifications.tasks import send_status_change_notification
        from apps.transactions.services.transaction_list_service import TransactionListService

        # Invalidate all transaction and tracking caches
        TransactionListService.invalidate_all_caches_for_transaction(escrow_transaction)

        # Determine if this was an automatic change
        is_automatic = kwargs.get("auto_transition", False)
        
        # Send status change notification asynchronously
        send_status_change_notification.apply_async(
            args=[escrow_transaction.id, previous_status, new_status, is_automatic]
        )



class EscrowTransactionUtility:

    @staticmethod
    def get_available_actions(transaction, user) -> Dict[str, Any]:
        """
        Get available actions for a user on a specific transaction

        Returns:
            dict: Available actions with metadata
        """
        is_buyer = user == transaction.buyer
        is_seller = user == transaction.seller
        user_type = "BUYER" if is_buyer else "SELLER"

        if not (is_buyer or is_seller) and not getattr(user, "is_staff", False):
            return {"available_actions": [], "user_role": "none"}

        current_status = transaction.status
        available_transitions = []

        if getattr(user, "is_staff", False):
            # Staff can perform any transition
            all_statuses = [
                "initiated",
                "payment_received",
                "shipped",
                "delivered",
                "inspection",
                "completed",
                "disputed",
                "funds_released",
                "refunded",
                "cancelled",
            ]
            available_transitions = [s for s in all_statuses if s != current_status]
        else:
            transitions = EscrowTransactionService.VALID_TRANSITIONS.get(user_type, {})
            available_transitions = transitions.get(current_status, [])

        # Add metadata for each action
        actions_with_metadata = []
        for action in available_transitions:
            action_data = {
                "status": action,
                "requires_tracking": action
                in EscrowTransactionService.STATUSES_REQUIRING_TRACKING,
                "has_time_limit": action
                in EscrowTransactionService.STATUSES_WITH_TIME_LIMITS,
                "description": EscrowTransactionUtility._get_action_description(
                    action, user_type
                ),
            }
            actions_with_metadata.append(action_data)

        return {
            "available_actions": actions_with_metadata,
            "user_role": (
                user_type.lower() if not getattr(user, "is_staff", False) else "staff"
            ),
            "current_status": current_status,
        }

    @staticmethod
    def _get_action_description(action: str, user_type: str) -> str:
        """Get human-readable description for actions"""
        descriptions = {
            "BUYER": {
                "cancelled": "Cancel this transaction",
                "delivered": "Confirm that you received the item",
                "inspection": "Start the inspection period",
                "completed": "Complete the transaction (release funds)",
                "disputed": "Open a dispute for this transaction",
            },
            "SELLER": {
                "payment_received": "Confirm payment has been received",
                "shipped": "Mark item as shipped",
                "funds_released": "Confirm funds have been withdrawn",
                "cancelled": "Cancel this transaction",
            },
        }

        return descriptions.get(user_type, {}).get(action, f"Update status to {action}")

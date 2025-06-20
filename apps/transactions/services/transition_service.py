from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from typing import Optional, Dict, Any
import logging

from apps.transactions.models import EscrowTransaction, EscrowTimeout
from apps.transactions.services.escrow_services import EscrowTransactionService

from apps.transactions.config.escrow_transition import EscrowTransitionConfig

logger = logging.getLogger(__name__)


class EscrowTransitionService:
    """
    Enhanced service for handling escrow transitions with proper task scheduling
    Builds upon the existing EscrowTransactionService
    """

    @classmethod
    @transaction.atomic
    def transition_with_scheduling(
        cls,
        escrow_transaction: EscrowTransaction,
        new_status: str,
        user,
        notes: str = "",
        tracking_number: Optional[str] = None,
        shipping_carrier: Optional[str] = None,
        **kwargs,
    ) -> EscrowTransaction:
        """
        Handle status transition with automatic task scheduling

        This method:
        1. Validates and performs the status transition
        2. Cancels any existing scheduled tasks
        3. Schedules new tasks if needed
        4. Tracks all scheduled tasks
        """

        try:
            # 1. Store the previous status
            previous_status = escrow_transaction.status

            # 2. Cancel any existing active timeouts for this transaction
            cancelled_count = EscrowTimeout.cancel_active_timeouts_for_transaction(
                escrow_transaction.id
            )

            if cancelled_count > 0:
                logger.info(
                    f"Cancelled {cancelled_count} active timeouts for transaction {escrow_transaction.id}"
                )

            # 3. Perform the status transition using existing service
            updated_transaction = (
                EscrowTransactionService.update_escrow_transaction_status(
                    escrow_transaction=escrow_transaction,
                    status=new_status,
                    user=user,
                    notes=notes,
                    tracking_number=tracking_number,
                    shipping_carrier=shipping_carrier,
                    **kwargs,
                )
            )

            # 4. Schedule new timeout if needed for the new status
            cls._schedule_timeout_for_status(updated_transaction, new_status)

            logger.info(
                f"Successfully transitioned transaction {escrow_transaction.id} "
                f"from {previous_status} to {new_status}"
            )

            return updated_transaction

        except Exception as e:
            logger.error(
                f"Failed to transition transaction {escrow_transaction.id} "
                f"from {escrow_transaction.status} to {new_status}: {str(e)}"
            )
            raise

    @classmethod
    def _schedule_timeout_for_status(cls, transaction: EscrowTransaction, status: str):
        """Schedule timeout task for a specific status if needed"""

        timeout_config = EscrowTransitionConfig.get_timeout_config(status)
        if not timeout_config:
            # No timeout needed for this status
            return

        # Calculate expiration time
        expires_at = timezone.now() + timedelta(days=timeout_config["days"])

        # Schedule the Celery task
        task_result = timeout_config["task"].apply_async(
            args=[transaction.id],
            countdown=timeout_config["days"] * 86400,  # Convert to seconds
        )

        # Create timeout tracking record
        timeout_record = EscrowTimeout.objects.create(
            transaction=transaction,
            timeout_type=timeout_config["timeout_type"],
            from_status=status,
            to_status=timeout_config["to_status"],
            expires_at=expires_at,
            celery_task_id=task_result.id,
        )

        logger.info(
            f"Scheduled {timeout_config['timeout_type']} timeout for transaction {transaction.id} "
            f"(expires at {expires_at}, task_id: {task_result.id})"
        )

        return timeout_record

    @classmethod
    def cancel_scheduled_timeouts(
        cls, transaction_id: int, timeout_type: Optional[str] = None
    ):
        """Cancel scheduled timeouts for a transaction"""
        return EscrowTimeout.cancel_active_timeouts_for_transaction(
            transaction_id, timeout_type
        )

    @classmethod
    def get_active_timeouts(cls, transaction_id: int) -> list:
        """Get all active timeouts for a transaction"""
        return list(
            EscrowTimeout.objects.filter(
                transaction_id=transaction_id, is_cancelled=False, is_executed=False
            )
        )

    @classmethod
    def reschedule_timeout(
        cls,
        transaction: EscrowTransaction,
        timeout_type: str,
        new_expires_at: timezone.datetime,
    ):
        """Reschedule an existing timeout to a new expiration time"""

        # Cancel existing timeout of this type
        existing_timeout = EscrowTimeout.get_active_timeout(
            transaction.id, timeout_type
        )
        if existing_timeout:
            existing_timeout.cancel("Rescheduled to new time")

        # Get the timeout config
        timeout_config = None
        for status, config in EscrowTransitionConfig.TIMEOUT_CONFIGS.items():
            if config["timeout_type"] == timeout_type:
                timeout_config = config
                break

        if not timeout_config:
            raise ValueError(f"Unknown timeout type: {timeout_type}")

        # Calculate countdown in seconds
        countdown = (new_expires_at - timezone.now()).total_seconds()
        if countdown <= 0:
            raise ValueError("Cannot schedule timeout in the past")

        # Schedule new task
        task_result = timeout_config["task"].apply_async(
            args=[transaction.id],
            countdown=int(countdown),
        )

        # Create new timeout record
        new_timeout = EscrowTimeout.objects.create(
            transaction=transaction,
            timeout_type=timeout_type,
            from_status=transaction.status,
            to_status=timeout_config["to_status"],
            expires_at=new_expires_at,
            celery_task_id=task_result.id,
        )

        logger.info(
            f"Rescheduled {timeout_type} timeout for transaction {transaction.id} "
            f"to {new_expires_at} (task_id: {task_result.id})"
        )

        return new_timeout


class EscrowTransitionUtility:
    """Utility methods for escrow transitions"""

    @staticmethod
    def get_transition_info(transaction: EscrowTransaction) -> Dict[str, Any]:
        """Get comprehensive information about a transaction's transition state"""

        active_timeouts = EscrowTransitionService.get_active_timeouts(transaction.id)

        return {
            "current_status": transaction.status,
            "active_timeouts": [
                {
                    "timeout_type": timeout.timeout_type,
                    "to_status": timeout.to_status,
                    "expires_at": timeout.expires_at,
                    "time_remaining": (
                        (timeout.expires_at - timezone.now()).total_seconds()
                        if timeout.expires_at > timezone.now()
                        else 0
                    ),
                    "is_expired": timeout.is_expired,
                }
                for timeout in active_timeouts
            ],
            "has_scheduled_transitions": len(active_timeouts) > 0,
            "next_automatic_transition": (
                min(active_timeouts, key=lambda t: t.expires_at)
                if active_timeouts
                else None
            ),
        }

    @staticmethod
    def get_timeout_history(transaction: EscrowTransaction) -> list:
        """Get the complete timeout history for a transaction"""
        return list(
            EscrowTimeout.objects.filter(transaction=transaction).order_by(
                "-created_at"
            )
        )

    @staticmethod
    def is_transition_automatic(
        transaction_id: int, from_status: str, to_status: str
    ) -> bool:
        """Check if a specific transition was performed automatically"""
        return EscrowTimeout.objects.filter(
            transaction_id=transaction_id,
            from_status=from_status,
            to_status=to_status,
            is_executed=True,
        ).exists()


# Convenience methods for common operations
class EscrowTransitionHelpers:
    """Helper methods for common escrow transition operations"""

    @staticmethod
    def extend_inspection_period(transaction: EscrowTransaction, additional_days: int):
        """Extend the inspection period for a transaction"""
        if transaction.status != "inspection":
            raise ValueError(
                "Can only extend inspection period for transactions in inspection status"
            )

        new_expires_at = timezone.now() + timedelta(days=additional_days)
        return EscrowTransitionService.reschedule_timeout(
            transaction, "inspection_end", new_expires_at
        )

    @staticmethod
    def extend_shipping_deadline(transaction: EscrowTransaction, additional_days: int):
        """Extend the shipping deadline for a transaction"""
        if transaction.status != "payment_received":
            raise ValueError(
                "Can only extend shipping deadline for transactions with payment received"
            )

        new_expires_at = timezone.now() + timedelta(days=additional_days)
        return EscrowTransitionService.reschedule_timeout(
            transaction, "shipping", new_expires_at
        )

    @staticmethod
    def force_transition_now(
        transaction: EscrowTransaction, to_status: str, user, notes: str = ""
    ):
        """Force an immediate transition, cancelling any scheduled timeouts"""
        return EscrowTransitionService.transition_with_scheduling(
            transaction, to_status, user, notes=notes
        )

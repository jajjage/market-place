# services/inventory_extension.py
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.products.services import InventoryService
from apps.transactions.models import EscrowTransaction, TransactionHistory


class ExtendedInventoryService(InventoryService):
    """Extended service with additional methods for automated escrow transitions"""

    @staticmethod
    @transaction.atomic
    def auto_move_to_inspection(
        transaction_id, notes="Auto-moved to inspection after delivery grace period"
    ):
        """
        Automatically move a transaction from delivered to inspection status.

        Args:
            transaction_id: ID of the escrow transaction
            notes: Descriptive notes for the status change

        Returns:
            The updated escrow transaction or None if the operation failed
        """
        try:
            escrow_transaction = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id, status="delivered"
            )

            # Set inspection end date based on the configured inspection period
            inspection_end_date = timezone.now() + timedelta(
                days=escrow_transaction.inspection_period_days
            )

            # Update status and inspection end date
            escrow_transaction.status = "inspection"
            escrow_transaction.inspection_end_date = inspection_end_date
            escrow_transaction.save(update_fields=["status", "inspection_end_date"])

            # Create transaction history record
            TransactionHistory.objects.create(
                transaction=escrow_transaction,
                status="inspection",
                notes=notes,
                created_by=None,  # System-generated entry
            )

            return escrow_transaction
        except EscrowTransaction.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def auto_complete_after_inspection(
        transaction_id, notes="Auto-completed after inspection period expired"
    ):
        """
        Automatically complete a transaction after the inspection period expires.

        Args:
            transaction_id: ID of the escrow transaction
            notes: Descriptive notes for the status change

        Returns:
            The updated product or None if the operation failed
        """
        try:
            escrow_transaction = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id,
                status="inspection",
                inspection_end_date__lte=timezone.now(),
            )

            # Use the base release_from_escrow method to complete the transaction
            product = InventoryService.release_from_escrow(
                product=escrow_transaction.product,
                escrow_transaction=escrow_transaction,
                release_type="deduct",  # Mark as sold
                notes=notes,
            )

            return product
        except EscrowTransaction.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def auto_refund_disputed_transaction(
        transaction_id, notes="Auto-refunded after extended dispute period"
    ):
        """
        Automatically refund a transaction that has been in disputed status for too long.

        Args:
            transaction_id: ID of the escrow transaction
            notes: Descriptive notes for the status change

        Returns:
            The updated product or None if the operation failed
        """
        try:
            escrow_transaction = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id, status="disputed"
            )

            # Use the base release_from_escrow method to refund the transaction
            product = InventoryService.release_from_escrow(
                product=escrow_transaction.product,
                escrow_transaction=escrow_transaction,
                release_type="return",  # Return to available inventory
                notes=notes,
            )

            return product
        except EscrowTransaction.DoesNotExist:
            return None

    @staticmethod
    def get_transactions_requiring_attention():
        """
        Get a list of transactions that may require system attention:
        - Delivered items with expired grace periods
        - Inspections with expired periods
        - Disputed items with extended disputes

        Returns:
            Dictionary with counts of transactions requiring attention
        """
        now = timezone.now()

        # This would need additional fields in your model to track when status changes occurred
        # For now, we'll just look at inspection end dates which are already tracked
        expired_inspections = EscrowTransaction.objects.filter(
            status="inspection", inspection_end_date__lt=now
        ).count()

        return {
            "expired_inspections": expired_inspections,
            # Add other metrics as your model allows
        }

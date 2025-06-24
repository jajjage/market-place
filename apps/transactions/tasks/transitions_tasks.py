import logging
from celery import shared_task
from django.db import transaction, models
from django.utils import timezone


from apps.core.tasks import BaseTaskWithRetry
from apps.products.product_inventory.services import InventoryService

from apps.transactions.models import (
    EscrowTransaction,
    EscrowTimeout,
    TransactionHistory,
)

logger = logging.getLogger("transition_tasks")


class TransitionTaskMixin:
    """Mixin to provide common functionality for transition tasks"""

    @staticmethod
    def _get_and_validate_timeout(
        task_id: str, transaction_id: int, expected_status: str
    ) -> tuple:
        """
        Get and validate timeout record for a task

        Returns:
            tuple: (timeout_record, transaction, is_valid)
        """
        try:
            # Find the timeout record for this task
            timeout_record = EscrowTimeout.objects.get(celery_task_id=task_id)

            # Validate the timeout is still active
            if not timeout_record.is_active:
                logger.info(
                    f"Timeout {timeout_record.id} is no longer active (task_id: {task_id})"
                )
                return timeout_record, None, False

            # Get the transaction with lock
            transaction_obj = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id, status=expected_status
            )

            # Validate the timeout belongs to this transaction
            if timeout_record.transaction_id != transaction_id:
                logger.error(
                    f"Timeout {timeout_record.id} does not belong to transaction {transaction_id}"
                )
                return timeout_record, None, False

            return timeout_record, transaction_obj, True

        except EscrowTimeout.DoesNotExist:
            logger.error(f"Timeout record not found for task_id: {task_id}")
            return None, None, False
        except EscrowTransaction.DoesNotExist:
            logger.info(
                f"Transaction {transaction_id} not found or no longer in expected status '{expected_status}'"
            )
            # Still try to get timeout to mark it as cancelled
            try:
                timeout_record = EscrowTimeout.objects.get(celery_task_id=task_id)
                timeout_record.cancel("Transaction no longer in expected status")
                return timeout_record, None, False
            except EscrowTimeout.DoesNotExist:
                return None, None, False

    @staticmethod
    def _execute_transition(
        timeout_record: EscrowTimeout,
        transaction_obj: EscrowTransaction,
        to_status: str,
        notes: str,
    ) -> bool:
        """
        Execute the actual transition and update timeout record

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from django.contrib.auth import get_user_model
            from apps.transactions.services.escrow_services import (
                EscrowTransactionService,
            )

            User = get_user_model()
            admin_user = User.objects.filter(is_staff=True).first()

            # Perform the transition
            EscrowTransactionService.update_escrow_transaction_status(
                escrow_transaction=transaction_obj,
                new_status=to_status,
                notes=notes,
                user=admin_user,  # Set user as Admin
                # Mark this as an automatic transition
                auto_transition=True,
            )

            # Mark timeout as executed
            timeout_record.execute(f"Automatically transitioned to {to_status}")

            logger.info(
                f"Successfully executed automatic transition for transaction {transaction_obj.id} to {to_status}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to execute transition for transaction {transaction_obj.id}: {str(e)}"
            )
            timeout_record.cancel(f"Transition failed: {str(e)}")
            return False


@shared_task(bind=True, base=BaseTaskWithRetry)
def schedule_auto_inspection(self, transaction_id):
    """
    Task to automatically move a transaction from delivered to inspection status
    after the grace period has expired if buyer hasn't acted.
    """
    task_id = self.request.id

    try:
        with transaction.atomic():
            # Get and validate the timeout record
            timeout_record, escrow_txn, is_valid = (
                TransitionTaskMixin._get_and_validate_timeout(
                    task_id, transaction_id, "delivered"
                )
            )

            if not is_valid:
                return f"Task {task_id} is no longer valid for transaction {transaction_id}"

            # Release from escrow and mark as completed
            if not escrow_txn.product.requires_inspection:
                previous_status = escrow_txn.status
                product = InventoryService.release_from_escrow(
                    product=escrow_txn.product,
                    escrow_transaction=escrow_txn,
                    previous_status=previous_status,
                    release_type="deduct",  # Item is sold, remove from total inventory
                    notes="Transaction automatically completed after inspection period expired.",
                )

                # Mark timeout as executed
                timeout_record.execute(
                    "Automatically completed after delivered no inspection period expired"
                )

                logger.info(
                    f"Transaction {transaction_id} automatically completed after delivered no inspection"
                )
                return f"Transaction {transaction_id} automatically completed after delivered no inspection"

            # Execute the transition
            success = TransitionTaskMixin._execute_transition(
                timeout_record,
                escrow_txn,
                "inspection",
                "Automatically moved to inspection after delivery grace period.",
            )

            if success:
                return f"Transaction {transaction_id} automatically moved to inspection status"
            else:
                return (
                    f"Failed to automatically transition transaction {transaction_id}"
                )

    except Exception as e:
        logger.error(
            f"Unexpected error in schedule_auto_inspection for transaction {transaction_id}: {str(e)}"
        )
        return f"Task failed with error: {str(e)}"


@shared_task(bind=True, base=BaseTaskWithRetry)
def schedule_auto_completion(self, transaction_id):
    """
    Task to automatically complete a transaction after the inspection period expires
    if the buyer hasn't disputed or completed it manually.
    """
    task_id = self.request.id

    try:
        with transaction.atomic():
            # Get and validate the timeout record
            timeout_record, escrow_txn, is_valid = (
                TransitionTaskMixin._get_and_validate_timeout(
                    task_id, transaction_id, "inspection"
                )
            )

            if not is_valid:
                return f"Task {task_id} is no longer valid for transaction {transaction_id}"

            # Additional validation: check if inspection period has actually ended
            if (
                escrow_txn.inspection_end_date
                and escrow_txn.inspection_end_date > timezone.now()
            ):
                logger.warning(
                    f"Inspection period for transaction {transaction_id} has not ended yet"
                )
                return (
                    f"Inspection period for transaction {transaction_id} has not ended"
                )

            # Release from escrow and mark as completed
            previous_status = escrow_txn.status
            product = InventoryService.release_from_escrow(
                product=escrow_txn.product,
                escrow_transaction=escrow_txn,
                previous_status=previous_status,
                release_type="deduct",  # Item is sold, remove from total inventory
                notes="Transaction automatically completed after inspection period expired.",
            )

            # Mark timeout as executed
            timeout_record.execute(
                "Automatically completed after inspection period expired"
            )

            logger.info(
                f"Transaction {transaction_id} automatically completed after inspection period"
            )
            return f"Transaction {transaction_id} automatically completed after inspection period"

    except Exception as e:
        logger.error(
            f"Unexpected error in schedule_auto_completion for transaction {transaction_id}: {str(e)}"
        )
        return f"Task failed with error: {str(e)}"


@shared_task(bind=True, base=BaseTaskWithRetry)
def auto_refund_disputed_transaction(self, transaction_id):
    """
    Task to automatically refund a transaction that has been in disputed status
    for too long without resolution.
    """
    task_id = self.request.id

    try:
        with transaction.atomic():
            # Get and validate the timeout record
            timeout_record, escrow_txn, is_valid = (
                TransitionTaskMixin._get_and_validate_timeout(
                    task_id, transaction_id, "disputed"
                )
            )

            if not is_valid:
                return f"Task {task_id} is no longer valid for transaction {transaction_id}"

            # Return inventory to available and mark as refunded
            product = InventoryService.release_from_escrow(
                product=escrow_txn.product,
                escrow_transaction=escrow_txn,
                release_type="return",  # Return to available inventory
                notes="Transaction automatically refunded after extended dispute period with no resolution.",
            )

            # Mark timeout as executed
            timeout_record.execute(
                "Automatically refunded after extended dispute period"
            )

            # In a real system, this would also process the refund with your payment processor
            # PaymentService.process_refund(escrow_txn)

            logger.info(
                f"Transaction {transaction_id} automatically refunded after extended dispute period"
            )
            return f"Transaction {transaction_id} automatically refunded after extended dispute period"

    except Exception as e:
        logger.error(
            f"Unexpected error in auto_refund_disputed_transaction for transaction {transaction_id}: {str(e)}"
        )
        return f"Task failed with error: {str(e)}"


@shared_task(bind=True, base=BaseTaskWithRetry)
def schedule_shipping_timeout(self, transaction_id):
    """
    Task to handle shipping timeout - either cancel transaction or notify admin
    """
    task_id = self.request.id

    try:
        with transaction.atomic():
            # Get and validate the timeout record
            timeout_record, escrow_txn, is_valid = (
                TransitionTaskMixin._get_and_validate_timeout(
                    task_id, transaction_id, "payment_received"
                )
            )

            if not is_valid:
                return f"Task {task_id} is no longer valid for transaction {transaction_id}"

            # For shipping timeout, we might want to cancel the transaction
            # or notify admin instead of automatically transitioning

            # Option 1: Auto-cancel the transaction
            success = TransitionTaskMixin._execute_transition(
                timeout_record,
                escrow_txn,
                "cancelled",
                "Transaction cancelled due to shipping timeout - seller failed to ship within allowed time",
            )

            if success:
                # Return inventory to available
                InventoryService.release_from_escrow(
                    product=escrow_txn.product,
                    escrow_transaction=escrow_txn,
                    release_type="return",
                    notes="Returned to inventory due to shipping timeout",
                )

                # Send notification to both parties
                # NotificationService.send_shipping_timeout_notification(escrow_txn)

                return f"Transaction {transaction_id} cancelled due to shipping timeout"
            else:
                return f"Failed to cancel transaction {transaction_id} due to shipping timeout"

    except Exception as e:
        logger.error(
            f"Unexpected error in schedule_shipping_timeout for transaction {transaction_id}: {str(e)}"
        )
        return f"Task failed with error: {str(e)}"


@shared_task(bind=True, base=BaseTaskWithRetry)
def check_expired_transactions(self):
    """
    Periodic task to catch any transactions that may have missed their scheduled tasks.
    This acts as a safety net for the automatic transition system.
    """
    try:
        now = timezone.now()

        # Find timeouts that should have been executed but weren't
        expired_timeouts = EscrowTimeout.objects.filter(
            expires_at__lt=now, is_executed=False, is_cancelled=False
        )

        results = []

        for timeout in expired_timeouts:
            try:
                # Get the appropriate task for this timeout type
                task_map = {
                    "inspection_start": schedule_auto_inspection,
                    "inspection_end": schedule_auto_completion,
                    "dispute_refund": auto_refund_disputed_transaction,
                    "shipping": schedule_shipping_timeout,
                }

                task_func = task_map.get(timeout.timeout_type)
                if task_func:
                    # Execute the task immediately
                    result = task_func.apply_async(args=[timeout.transaction_id])
                    results.append(
                        f"Executed missed {timeout.timeout_type} for transaction {timeout.transaction_id}"
                    )
                else:
                    # Unknown timeout type, mark as cancelled
                    timeout.cancel(f"Unknown timeout type: {timeout.timeout_type}")
                    results.append(
                        f"Cancelled unknown timeout type {timeout.timeout_type} for transaction {timeout.transaction_id}"
                    )

            except Exception as e:
                logger.error(f"Failed to handle expired timeout {timeout.id}: {str(e)}")
                results.append(
                    f"Failed to handle expired timeout {timeout.id}: {str(e)}"
                )

        logger.info(f"Processed {len(expired_timeouts)} expired timeouts")
        return {"processed_count": len(expired_timeouts), "results": results}

    except Exception as e:
        logger.error(f"Error in check_expired_transactions: {str(e)}")
        return f"Task failed with error: {str(e)}"


@shared_task(bind=True, base=BaseTaskWithRetry)
def cleanup_completed_timeouts(self, days_old=30):
    """
    Cleanup old completed/cancelled timeout records to keep the database clean
    """
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)

        # Delete old completed/cancelled timeouts
        deleted_count = EscrowTimeout.objects.filter(
            models.Q(is_executed=True) | models.Q(is_cancelled=True),
            updated_at__lt=cutoff_date,
        ).delete()[0]

        logger.info(f"Cleaned up {deleted_count} old timeout records")
        return (
            f"Cleaned up {deleted_count} old timeout records older than {days_old} days"
        )

    except Exception as e:
        logger.error(f"Error in cleanup_completed_timeouts: {str(e)}")
        return f"Cleanup task failed with error: {str(e)}"


# ------------------------------------------------------------------------------
# Flutterwave Escrow transaction  task to trigger after payment verification
# ------------------------------------------------------------------------------
@shared_task(bind=True, base=BaseTaskWithRetry)
def process_payment_received(transaction_id):
    """
    Process a transaction that has received payment.
    This would integrate with your payment system to verify funds have cleared.
    """
    try:
        # In a real system, this would verify payment with payment processor
        # For now, we'll just log that payment processing was attempted
        escrow_txn = EscrowTransaction.objects.get(
            id=transaction_id, status="payment_received"
        )

        # Create history record to show payment processing occurred
        TransactionHistory.objects.create(
            transaction=escrow_txn,
            status="payment_received",
            notes="Payment verification process completed.",
        )

        return f"Payment for transaction {transaction_id} processed successfully"
    except EscrowTransaction.DoesNotExist:
        return (
            f"Transaction {transaction_id} not found or not in payment_received status"
        )

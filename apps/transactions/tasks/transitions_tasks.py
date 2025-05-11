# apps/transactions/tasks.py
from celery import shared_task
from django.db import transaction
from django.utils import timezone


from apps.transactions.models import EscrowTransaction, TransactionHistory
from apps.products.services.inventory import InventoryService


@shared_task
def schedule_auto_inspection(transaction_id):
    """
    Task to automatically move a transaction from delivered to inspection status
    after the grace period has expired if buyer hasn't acted.
    """
    try:
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            escrow_txn = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id, status="delivered"
            )

            # Move to inspection status
            updated_txn = InventoryService.update_escrow_transaction_status(
                escrow_transaction=escrow_txn,
                status="inspection",
                notes="Automatically moved to inspection after delivery grace period.",
            )

            return (
                f"Transaction {transaction_id} automatically moved to inspection status"
            )
    except EscrowTransaction.DoesNotExist:
        # Transaction doesn't exist or is no longer in delivered status
        return (
            f"Transaction {transaction_id} not found or no longer in delivered status"
        )


@shared_task
def schedule_auto_completion(transaction_id):
    """
    Task to automatically complete a transaction after the inspection period expires
    if the buyer hasn't disputed or completed it manually.
    """
    try:
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            escrow_txn = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id,
                status="inspection",
                inspection_end_date__lte=timezone.now(),
            )

            # Release from escrow and mark as completed
            product = InventoryService.release_from_escrow(
                product=escrow_txn.product,
                escrow_transaction=escrow_txn,
                release_type="deduct",  # Item is sold, remove from total inventory
                notes="Transaction automatically completed after inspection period expired.",
            )

            return f"Transaction {transaction_id} automatically completed after inspection period"
    except EscrowTransaction.DoesNotExist:
        # Transaction doesn't exist, is no longer in inspection status, or inspection period hasn't ended
        return f"Transaction {transaction_id} not eligible for auto-completion"


# ------------------------------------------------------------------------------
# Flutterwave Escrow transaction  task to trigger after payment verification
# ------------------------------------------------------------------------------
@shared_task
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


@shared_task
def auto_refund_disputed_transaction(transaction_id):
    """
    Task to automatically refund a transaction that has been in disputed status
    for too long without resolution.
    """
    try:
        with transaction.atomic():
            escrow_txn = EscrowTransaction.objects.select_for_update().get(
                id=transaction_id, status="disputed"
            )

            # Return inventory to available and mark as refunded
            product = InventoryService.release_from_escrow(
                product=escrow_txn.product,
                escrow_transaction=escrow_txn,
                release_type="return",  # Return to available inventory
                notes="Transaction automatically refunded after extended dispute period with no resolution.",
            )

            # In a real system, this would also process the refund with your payment processor

            return f"Transaction {transaction_id} automatically refunded after extended dispute period"
    except EscrowTransaction.DoesNotExist:
        return f"Transaction {transaction_id} not found or no longer in disputed status"


@shared_task
def check_expired_transactions():
    """
    Periodic task to catch any transactions that may have missed their scheduled tasks.
    This acts as a safety net for the automatic transition system.
    """
    now = timezone.now()

    # Check for expired inspection periods
    expired_inspections = EscrowTransaction.objects.filter(
        status="inspection", inspection_end_date__lt=now
    )

    for txn in expired_inspections:
        schedule_auto_completion.apply_async(args=[txn.id])

    # Check for stale delivered transactions
    # This requires knowing when they were marked as delivered, which would need a timestamp field
    # If you have such a field, you could implement similar logic here

    return f"Checked for expired transactions. Found {expired_inspections.count()} expired inspections."

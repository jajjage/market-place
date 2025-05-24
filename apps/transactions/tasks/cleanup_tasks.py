# apps/transactions/cleanup_tasks.py
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from apps.core.tasks import BaseTaskWithRetry
from apps.transactions.models import EscrowTransaction

# Default retention periods
DEFAULT_COMPLETED_RETENTION_DAYS = (
    90  # How long to keep completed transactions in active DB
)
DEFAULT_CANCELLED_RETENTION_DAYS = (
    30  # How long to keep cancelled transactions in active DB
)


@shared_task(bind=True, base=BaseTaskWithRetry)
def clean_old_completed_transactions():
    """
    Archives or deletes old completed/cancelled/refunded transactions
    that are beyond the retention period.

    In a production system, this would typically move them to an archive
    table rather than deleting them.
    """
    now = timezone.now()

    # Get retention periods from settings or use defaults
    completed_retention = getattr(
        settings,
        "COMPLETED_TRANSACTION_RETENTION_DAYS",
        DEFAULT_COMPLETED_RETENTION_DAYS,
    )
    cancelled_retention = getattr(
        settings,
        "CANCELLED_TRANSACTION_RETENTION_DAYS",
        DEFAULT_CANCELLED_RETENTION_DAYS,
    )

    # Calculate cutoff dates
    completed_cutoff = now - timedelta(days=completed_retention)
    cancelled_cutoff = now - timedelta(days=cancelled_retention)

    # Get transactions to clean up
    old_completed = EscrowTransaction.objects.filter(
        status="completed", modified_at__lt=completed_cutoff
    )

    old_cancelled = EscrowTransaction.objects.filter(
        status__in=["cancelled", "refunded"], modified_at__lt=cancelled_cutoff
    )

    # In a real system, you would:
    # 1. Archive these to another table
    # 2. Then delete them from the active table

    # For this example, we'll just count them
    completed_count = old_completed.count()
    cancelled_count = old_cancelled.count()

    return f"Found {completed_count} old completed and {cancelled_count} old cancelled/refunded transactions to archive"


@shared_task(bind=True, base=BaseTaskWithRetry)
def check_stalled_transactions():
    """
    Identifies transactions that appear to be stuck in a non-final state
    for an extended period without any activity.
    """
    now = timezone.now()
    stalled_period = getattr(
        settings, "STALLED_TRANSACTION_DAYS", 14
    )  # Default: 14 days
    stalled_cutoff = now - timedelta(days=stalled_period)

    # Find transactions that haven't been updated in a while and are not in a final state
    stalled_transactions = EscrowTransaction.objects.filter(
        status__in=[
            "initiated",
            "payment_received",
            "shipped",
            "delivered",
            "inspection",
            "disputed",
        ],
        modified_at__lt=stalled_cutoff,
    )

    # In a real system, you might:
    # 1. Send notifications to admins about stalled transactions
    # 2. Send reminders to involved parties
    # 3. Auto-cancel very old stalled transactions

    stalled_count = stalled_transactions.count()
    if stalled_count > 0:
        # Log for admin review
        stalled_ids = list(stalled_transactions.values_list("id", flat=True))
        return f"Found {stalled_count} stalled transactions: {stalled_ids}"

    return "No stalled transactions found"

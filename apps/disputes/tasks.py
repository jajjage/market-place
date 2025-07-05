from celery import shared_task
from django.utils import timezone
from .models import Dispute, DisputeStatus
import logging

logger = logging.getLogger("dispute_performance")


@shared_task(bind=True, max_retries=3)
def update_transaction_status(self, transaction_id, new_status):
    """Update transaction status after dispute actions"""
    try:
        start_time = timezone.now()

        from apps.transactions.models import EscrowTransaction

        transaction = EscrowTransaction.objects.get(id=transaction_id)
        transaction.status = new_status
        transaction.save()

        # Invalidate transaction cache
        from apps.core.utils.cache_manager import CacheManager

        CacheManager.invalidate("transaction", id=transaction_id)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(
            f"Updated transaction {transaction_id} status to {new_status} in {duration:.2f}ms"
        )

    except Exception as exc:
        logger.error(f"Failed to update transaction status: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def cleanup_old_disputes():
    """Clean up old resolved disputes (run daily)"""
    from django.utils import timezone
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=365)  # Keep for 1 year

    old_disputes = Dispute.objects.filter(
        status__in=[
            DisputeStatus.RESOLVED_BUYER,
            DisputeStatus.RESOLVED_SELLER,
            DisputeStatus.CLOSED,
        ],
        updated_at__lt=cutoff_date,
    )

    count = old_disputes.count()
    old_disputes.delete()

    logger.info(f"Cleaned up {count} old disputes")

    return f"Cleaned up {count} old disputes"
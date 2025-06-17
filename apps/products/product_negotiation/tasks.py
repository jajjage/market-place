# apps/products/product_negotiation/tasks.py
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from celery import shared_task

from apps.core.utils.cache_manager import CacheManager
from apps.products.product_negotiation.models import (
    PriceNegotiation,
    NegotiationHistory,
)
from apps.products.product_negotiation.services import NegotiationNotificationService

logger = logging.getLogger("negotiation_performance")


@shared_task
def expire_old_negotiations():
    """
    Expire old negotiations that have passed their deadline.
    Run daily to clean up stale negotiations.
    """
    start_time = timezone.now()

    # Get expiry threshold from settings
    expiry_hours = getattr(settings, "NEGOTIATION_SETTINGS", {}).get(
        "AUTO_EXPIRE_HOURS", 168
    )
    expiry_threshold = timezone.now() - timedelta(hours=expiry_hours)

    # Find negotiations to expire
    negotiations_to_expire = PriceNegotiation.objects.filter(
        status__in=["pending", "countered"], updated_at__lt=expiry_threshold
    )

    expired_count = 0

    for negotiation in negotiations_to_expire:
        # Update status to expired
        negotiation.status = "rejected"  # or create an 'expired' status
        negotiation.save()

        # Record in history
        NegotiationHistory.objects.create(
            negotiation=negotiation,
            action="price_rejected",
            user=negotiation.seller,  # System action
            notes=f"Negotiation expired after {expiry_hours} hours of inactivity",
        )

        # Send expiration notifications
        NegotiationNotificationService.notify_negotiation_expired(negotiation)

        # Invalidate related caches
        CacheManager.invalidate("negotiation", id=negotiation.id)
        CacheManager.invalidate("product", id=negotiation.product.id)

        expired_count += 1

    duration = (timezone.now() - start_time).total_seconds()
    logger.info(f"Expired {expired_count} negotiations in {duration:.2f} seconds")

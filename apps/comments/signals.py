from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.transactions.models import EscrowTransaction
from .models import UserRating
from .tasks import setup_rating_eligibility, update_rating_stats
import logging

logger = logging.getLogger("ratings_performance")


@receiver(post_save, sender=EscrowTransaction)
def handle_transaction_completion(sender, instance, created, **kwargs):
    """Handle transaction completion - setup rating eligibility"""
    if (
        not created
        and instance.status not in ["completed", "funds_released"]
        and instance.status_changed_at
    ):
        # Check if we've already processed this completion
        if not hasattr(instance, "_rating_setup_done"):
            # Trigger async task for rating setup
            setup_rating_eligibility.delay(instance.id)

            # Mark as processed to avoid double processing
            instance._rating_setup_done = True

            logger.info(
                f"Transaction {instance.id} completed, rating eligibility setup queued"
            )


@receiver(post_save, sender=UserRating)
def handle_rating_created(sender, instance, created, **kwargs):
    """Handle new rating creation"""
    if created:
        # Trigger async tasks
        update_rating_stats.delay(instance.to_user.id)

        # Invalidate related caches immediately
        from .services import RatingService

        RatingService.invalidate_user_rating_cache(instance.to_user.id)
        RatingService.invalidate_user_rating_cache(instance.from_user.id)

        logger.info(f"New rating created: {instance.id}, async tasks queued")

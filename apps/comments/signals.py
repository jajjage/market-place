from datetime import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from apps.transactions.models import EscrowTransaction
from .models import UserRating
from .tasks import setup_rating_eligibility, update_rating_stats
import logging

logger = logging.getLogger("ratings_performance")


@receiver(post_save, sender=EscrowTransaction)
def handle_transaction_completion(sender, instance, created, **kwargs):
    # only run when status just moved into a “completed” state
    just_completed = (
        not created
        and instance.status in ["completed", "funds_released"]
        and instance.status_changed_at  # you already track this
    )
    if not just_completed or instance.rating_setup_done:
        return

    def enqueue_and_mark():
        # 1. enqueue the Celery task
        setup_rating_eligibility.delay(instance.id)

        # 2. mark the DB flag so we never enqueue again
        # use .filter/.update to avoid a second save() signal
        EscrowTransaction.objects.filter(pk=instance.pk).update(
            rating_setup_done=True,
            # optionally also update a timestamp, e.g.:
            rating_setup_done_at=timezone.now(),
        )
        logger.info(f"Transaction {instance.id}: rating task queued")

    # defer to after the outer transaction commits
    transaction.on_commit(enqueue_and_mark)


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

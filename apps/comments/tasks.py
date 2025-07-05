# apps/comments/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from apps.core.tasks import BaseTaskWithRetry
from .models import UserRating, RatingEligibility
from .services import RatingService
from apps.transactions.models import EscrowTransaction
from apps.notifications.services.notification_service import NotificationService
import logging

logger = logging.getLogger("ratings_performance")


@shared_task(bind=True, base=BaseTaskWithRetry)
def setup_rating_eligibility(self, transaction_id):
    """Setup rating eligibility when transaction completes"""
    try:
        transaction = EscrowTransaction.objects.get(id=transaction_id)
        ALLOWED = {"completed", "funds_released"}
        status = transaction.status

        if status not in ALLOWED:
            logger.warning(
                f"Transaction {transaction_id} is not completed, skipping rating setup"
            )
            return

        eligibility, created = RatingEligibility.objects.get_or_create(
            transaction=transaction,
            defaults={
                "can_rate_from": transaction.status_changed_at,
                "rating_deadline": transaction.status_changed_at + timedelta(days=30),
                "reminder_sent": False,
                "final_reminder_sent": False,
            },
        )
        if created:
            logger.info(f"RatingEligibility created for transaction {transaction_id}")

            context = {
                "transaction_id": transaction.id,
                "seller_name": transaction.seller.get_full_name(),
                "expires_at": (
                    transaction.status_changed_at + timedelta(days=30)
                ).isoformat(),
            }
            NotificationService.send_notification(
                transaction.buyer, "rating_available", context
            )

            reminder_date = transaction.status_changed_at + timedelta(days=7)
            send_rating_reminder.apply_async(args=[transaction.id], eta=reminder_date)

    except EscrowTransaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found")
    except Exception as exc:
        logger.error(
            f"Error setting up rating eligibility for transaction {transaction_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=BaseTaskWithRetry)
def update_rating_stats(self, user_id):
    """Update rating statistics for a user"""
    try:
        stats = RatingService.get_user_rating_stats(user_id, use_cache=False)
        from apps.users.models import User
        user = User.objects.get(id=user_id)
        user.average_rating = stats["average_rating"]
        user.total_ratings = stats["total_ratings"]
        user.save(update_fields=["average_rating", "total_ratings"])
        logger.info(f"Rating stats updated for user {user_id}")
    except Exception as exc:
        logger.error(f"Error updating rating stats for user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=BaseTaskWithRetry)
def send_rating_reminder(transaction_id):
    """Send reminder email to rate transaction"""
    try:
        transaction = EscrowTransaction.objects.select_related("buyer", "seller").get(
            id=transaction_id
        )
        if not hasattr(transaction, "rating"):
            deadline = transaction.status_changed_at + timedelta(days=30)
            if timezone.now() < deadline:
                context = {
                    "transaction_id": transaction.id,
                    "seller_name": transaction.seller.get_full_name(),
                    "days_left": (deadline - timezone.now()).days,
                }
                NotificationService.send_notification(
                    transaction.buyer, "rating_reminder", context
                )
    except Exception as exc:
        logger.error(
            f"Error sending rating reminder for transaction {transaction_id}: {exc}"
        )


@shared_task(bind=True, base=BaseTaskWithRetry)
def send_rating_notifications(rating_id):
    """Send notifications when a rating is created"""
    try:
        rating = UserRating.objects.select_related(
            "from_user", "to_user", "transaction"
        ).get(id=rating_id)

        context = {
            "rating_id": rating.id,
            "rating_value": rating.rating,
            "transaction_id": rating.transaction.id,
        }
        NotificationService.send_notification(
            rating.to_user, "rating_received", context
        )

        NotificationService.delete_notification(
            rating.from_user,
            "rating_available",
            {"transaction_id": rating.transaction.id},
        )
        logger.info(f"Rating notifications sent for rating {rating_id}")
    except Exception as exc:
        logger.error(
            f"Error sending rating notifications for rating {rating_id}: {exc}"
        )


@shared_task(bind=True, base=BaseTaskWithRetry)
def cleanup_expired_rating_opportunities():
    """Clean up expired rating opportunities and send final notifications"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    expired_transactions = (
        EscrowTransaction.objects.filter(
            status="completed", status_changed_at__lt=thirty_days_ago
        )
        .exclude(rating__isnull=False)
        .select_related("buyer")
    )

    for transaction in expired_transactions:
        NotificationService.delete_notification(
            transaction.buyer,
            "rating_available",
            {"transaction_id": transaction.id},
        )
    logger.info(f"Cleaned up {len(expired_transactions)} expired rating opportunities")
    return len(expired_transactions)
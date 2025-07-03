from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta

from apps.core.tasks import BaseTaskWithRetry
from .models import UserRating, RatingEligibility
from .services import RatingService
from apps.transactions.models import EscrowTransaction

# from apps.notifications.models import Notification
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

        # Create RatingEligibility if not exists, set required fields
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
        else:
            logger.info(
                f"RatingEligibility already exists for transaction {transaction_id}"
            )

        # # Create rating eligibility notification
        # Notification.objects.create(
        #     user=transaction.buyer,
        #     type="RATING_AVAILABLE",
        #     title="Rate Your Purchase",
        #     message=f"You can now rate your transaction: {transaction.title}",
        #     data={
        #         "transaction_id": transaction.id,
        #         "seller_name": transaction.seller.get_full_name(),
        #         "expires_at": (
        #             transaction.status_changed_at + timedelta(days=30)
        #         ).isoformat(),
        #     },
        # )

        # Send email notification
        send_rating_available_email.delay(transaction.id)

        # Schedule reminder
        reminder_date = transaction.status_changed_at + timedelta(days=7)
        send_rating_reminder.apply_async(args=[transaction.id], eta=reminder_date)

        logger.info(
            f"Rating eligibility setup completed for transaction {transaction_id}"
        )

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
        # Force recalculation of stats (bypass cache)
        stats = RatingService.get_user_rating_stats(user_id, use_cache=False)

        # Update user profile with latest stats
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
def send_rating_available_email(transaction_id):
    """Send email notification when rating becomes available"""
    try:
        transaction = EscrowTransaction.objects.select_related("buyer", "seller").get(
            id=transaction_id
        )

        subject = f"Rate Your Purchase: {transaction.title}"
        message = f"""
        Hi {transaction.buyer.get_full_name()},
        <br />
        Your transaction has been completed successfully! You can now rate your experience with {transaction.seller.get_full_name()}.
        <br />
        Transaction: {transaction.title}
        <br />
        Completed: {transaction.status_changed_at.strftime('%B %d, %Y')}
        <br />
        Rating Deadline: {(transaction.status_changed_at + timedelta(days=30)).strftime('%B %d, %Y')}
        <br />
        Rate your experience: {settings.FRONTEND_URL}/transactions/{transaction.id}/rate
        <br />
        Best regards,
        The Team
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.buyer.email],
            fail_silently=False,
        )

        logger.info(f"Rating available email sent for transaction {transaction_id}")

    except Exception as exc:
        logger.error(
            f"Error sending rating available email for transaction {transaction_id}: {exc}"
        )


@shared_task(bind=True, base=BaseTaskWithRetry)
def send_rating_reminder(transaction_id):
    """Send reminder email to rate transaction"""
    try:
        transaction = EscrowTransaction.objects.select_related("buyer", "seller").get(
            id=transaction_id
        )

        # Check if already rated
        if hasattr(transaction, "rating"):
            logger.info(
                f"Transaction {transaction_id} already rated, skipping reminder"
            )
            return

        # Check if still within rating window
        deadline = transaction.status_changed_at + timedelta(days=30)
        if timezone.now() > deadline:
            logger.info(
                f"Rating deadline passed for transaction {transaction_id}, skipping reminder"
            )
            return

        subject = f"Reminder: Rate Your Purchase - {transaction.notes}"
        days_left = (deadline - timezone.now()).days

        message = f"""
        Hi {transaction.buyer.get_full_name()},
        <br />
        This is a friendly reminder that you can still rate your recent purchase.
        <br />
        Transaction: {transaction.notes}
        <br />
        Seller: {transaction.seller.get_full_name()}
        <br />
        Days remaining: {days_left}
        <br />
        Rate your experience: {settings.FRONTEND_URL}/transactions/{transaction.id}/rate
        <br />
        Best regards,
        The Team
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[transaction.buyer.email],
            fail_silently=False,
        )

        logger.info(f"Rating reminder email sent for transaction {transaction_id}")

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

        # # Notify seller about new rating
        # Notification.objects.create(
        #     user=rating.to_user,
        #     type="RATING_RECEIVED",
        #     title="New Rating Received",
        #     message=f"You received a {rating.rating}-star rating from {rating.from_user.get_full_name()}",
        #     data={
        #         "rating_id": rating.id,
        #         "rating_value": rating.rating,
        #         "transaction_id": rating.transaction.id,
        #     },
        # )

        # Send email to seller
        subject = f"New {rating.rating}-Star Rating Received"
        message = f"""
        Hi {rating.to_user.get_full_name()},
        <br />
        You received a new rating for your transaction!
        <br />
        Rating: {rating.rating} stars
        From: {rating.from_user.get_full_name()}
        Transaction: {rating.transaction.notes}
        Comment: {rating.comment[:200]}...
        <br />
        View your ratings: {settings.FRONTEND_URL}/profile/ratings
        <br />
        Best regards,
        The Team
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[rating.to_user.email],
            fail_silently=False,
        )

        # Remove pending rating notifications for buyer
        # Notification.objects.filter(
        #     user=rating.from_user,
        #     type="RATING_AVAILABLE",
        #     data__transaction_id=rating.transaction.id,
        # ).delete()

        logger.info(f"Rating notifications sent for rating {rating_id}")

    except Exception as exc:
        logger.error(
            f"Error sending rating notifications for rating {rating_id}: {exc}"
        )


@shared_task(bind=True, base=BaseTaskWithRetry)
def cleanup_expired_rating_opportunities():
    """Clean up expired rating opportunities and send final notifications"""
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Find completed transactions older than 30 days without ratings
    expired_transactions = (
        EscrowTransaction.objects.filter(
            status="completed", status_changed_at__lt=thirty_days_ago
        )
        .exclude(rating__isnull=False)
        .select_related("buyer")
    )

    count = 0
    for transaction in expired_transactions:
        # Remove related notifications
        # Notification.objects.filter(
        #     user=transaction.buyer,
        #     type__in=["RATING_AVAILABLE", "RATING_REMINDER"],
        #     data__transaction_id=transaction.id,
        # ).delete()
        count += 1

    logger.info(f"Cleaned up {count} expired rating opportunities")
    return count

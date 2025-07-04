from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import Dispute, DisputeStatus
import logging

logger = logging.getLogger("dispute_performance")


@shared_task(bind=True, max_retries=3)
def send_dispute_notification(self, dispute_id):
    """Send notification when dispute is created"""
    try:
        start_time = timezone.now()

        dispute = Dispute.objects.select_related(
            "opened_by", "transaction", "transaction__buyer", "transaction__seller"
        ).get(id=dispute_id)

        # Notify the other party
        if dispute.opened_by == dispute.transaction.buyer:
            recipient = dispute.transaction.seller
        else:
            recipient = dispute.transaction.buyer

        # Send email notification
        subject = f"Dispute Opened for Transaction #{dispute.transaction.id}"

        html_message = render_to_string(
            "emails/dispute_notification.html",
            {
                "dispute": dispute,
                "recipient": recipient,
            },
        )

        send_mail(
            subject=subject,
            message=f"A dispute has been opened for your transaction #{dispute.transaction.id}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            html_message=html_message,
            fail_silently=False,
        )

        # TODO: Send push notification if mobile app exists

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Sent dispute notification for {dispute_id} in {duration:.2f}ms")

    except Dispute.DoesNotExist:
        logger.error(f"Dispute {dispute_id} not found for notification")
    except Exception as exc:
        logger.error(f"Failed to send dispute notification: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_resolution_notification(self, dispute_id):
    """Send notification when dispute is resolved"""
    try:
        start_time = timezone.now()

        dispute = Dispute.objects.select_related(
            "opened_by",
            "resolved_by",
            "transaction",
            "transaction__buyer",
            "transaction__seller",
        ).get(id=dispute_id)

        # Notify both parties
        recipients = [dispute.transaction.buyer, dispute.transaction.seller]

        for recipient in recipients:
            subject = f"Dispute Resolved for Transaction #{dispute.transaction.id}"

            html_message = render_to_string(
                "emails/dispute_resolution.html",
                {
                    "dispute": dispute,
                    "recipient": recipient,
                },
            )

            send_mail(
                subject=subject,
                message=f"The dispute for transaction #{dispute.transaction.id} has been resolved",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                html_message=html_message,
                fail_silently=False,
            )

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(
            f"Sent resolution notification for {dispute_id} in {duration:.2f}ms"
        )

    except Dispute.DoesNotExist:
        logger.error(f"Dispute {dispute_id} not found for resolution notification")
    except Exception as exc:
        logger.error(f"Failed to send resolution notification: {exc}")
        raise self.retry(exc=exc, countdown=60)


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

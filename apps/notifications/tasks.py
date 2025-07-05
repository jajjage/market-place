from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from apps.core.tasks import BaseTaskWithRetry
from apps.transactions.models import EscrowTransaction
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import NotificationService


@shared_task(bind=True, base=BaseTaskWithRetry)
def send_notification_task(self, notification_id: int):
    """
    A task to send a notification using the appropriate channel.

    Args:
        notification_id: The ID of the notification to send.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        # TODO: Implement channel-specific sending logic
        # For now, we'll just log that the notification was "sent"
        print(
            f"Sending notification {notification.id} to {notification.recipient} via {notification.notification_type}"
        )
    except Notification.DoesNotExist:
        # Handle the case where the notification doesn't exist
        pass


@shared_task(bind=True, base=BaseTaskWithRetry)
def send_auto_transition_reminders(self):
    """
    Task to send reminders about upcoming automatic transitions.
    """
    now = timezone.now()
    upcoming_transitions = EscrowTransaction.objects.filter(
        is_auto_transition_scheduled=True,
        next_auto_transition_at__gt=now,
        next_auto_transition_at__lte=now + timedelta(hours=24),
    )

    for transaction in upcoming_transitions:
        context = {"transaction_id": transaction.id}
        NotificationService.send_notification(
            transaction.buyer, "upcoming_auto_transition", context
        )
        NotificationService.send_notification(
            transaction.seller, "upcoming_auto_transition", context
        )

    return f"Sent reminders for {len(upcoming_transitions)} upcoming transitions."


@shared_task(bind=True, base=BaseTaskWithRetry)
def send_status_change_notification(
    self, transaction_id, old_status, new_status, is_automatic=False
):
    """
    Task to send notification about status change.
    """
    try:
        transaction = EscrowTransaction.objects.get(id=transaction_id)
        context = {
            "transaction_id": transaction.id,
            "old_status": old_status,
            "new_status": new_status,
            "product_name": transaction.product.title,
        }
        NotificationService.send_notification(
            transaction.buyer, "transaction_status_update", context
        )
        NotificationService.send_notification(
            transaction.seller, "transaction_status_update", context
        )

        return f"Sent status change notification for transaction {transaction_id}"
    except EscrowTransaction.DoesNotExist:
        return f"Transaction {transaction_id} not found"

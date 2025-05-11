# apps/notifications/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from apps.transactions.models import EscrowTransaction
from apps.notifications.services import EscrowNotificationService


@shared_task
def send_auto_transition_reminders():
    """
    Task to send reminders about upcoming automatic transitions
    Runs periodically to notify users about actions they might want to take
    before automatic transitions occur
    """
    now = timezone.now()

    # Find transactions with upcoming auto-transitions in the next 24 hours
    upcoming_transitions = EscrowTransaction.objects.filter(
        is_auto_transition_scheduled=True,
        next_auto_transition_at__gt=now,
        next_auto_transition_at__lte=now + timedelta(hours=24),
    )

    # Count sent reminders by type
    reminders_sent = {"delivered": 0, "inspection": 0, "disputed": 0, "other": 0}

    # Send reminders for each transaction
    for transaction in upcoming_transitions:
        EscrowNotificationService.send_upcoming_auto_transition_reminder(transaction)

        # Update counter
        if transaction.status in reminders_sent:
            reminders_sent[transaction.status] += 1
        else:
            reminders_sent["other"] += 1

    # Return summary
    return (
        f"Sent reminders for {len(upcoming_transitions)} upcoming transitions: "
        f"{reminders_sent['delivered']} delivered, "
        f"{reminders_sent['inspection']} inspection, "
        f"{reminders_sent['disputed']} disputed, "
        f"{reminders_sent['other']} other"
    )


@shared_task
def send_status_change_notification(
    transaction_id, old_status, new_status, is_automatic=False
):
    """
    Task to send notification about status change
    This is used to decouple notification sending from the main request/response cycle

    Args:
        transaction_id: ID of the transaction
        old_status: Previous status
        new_status: New status
        is_automatic: Whether this was an automatic transition
    """
    try:
        transaction = EscrowTransaction.objects.get(id=transaction_id)
        EscrowNotificationService.send_status_change_notification(
            transaction, old_status, new_status, is_automatic
        )
        return f"Sent status change notification for transaction {transaction_id}"
    except EscrowTransaction.DoesNotExist:
        return f"Transaction {transaction_id} not found"

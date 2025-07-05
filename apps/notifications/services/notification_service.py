from typing import Dict, Any
from apps.notifications.models import Notification, NotificationTemplate
from apps.users.models import CustomUser as User


class NotificationService:
    """
    A centralized service for handling all notification-related operations.
    """

    @staticmethod
    def send_notification(
        recipient: User, notification_type: str, context: Dict[str, Any]
    ):
        from apps.notifications.tasks import send_notification_task

        """
        Creates a notification and triggers an asynchronous task to send it.

        Args:
            recipient: The user who should receive the notification.
            notification_type: The type of notification (maps to a NotificationTemplate).
            context: A dictionary of context data for the notification message.
        """
        try:
            template = NotificationTemplate.objects.get(name=notification_type)

            # Create the notification object
            notification = Notification.objects.create(
                recipient=recipient,
                message=template.body.format(**context),
                notification_type=notification_type,
                data=context,
            )

            # Trigger the async task to send the notification
            send_notification_task.delay(notification.id)

        except NotificationTemplate.DoesNotExist:
            # Handle the case where the template doesn't exist
            # You might want to log this error
            pass

    @staticmethod
    def delete_notification(
        recipient: "User", notification_type: str, context_filter: Dict[str, Any]
    ):
        """
        Deletes notifications matching the given criteria.

        Args:
            recipient: The user whose notifications should be deleted.
            notification_type: The type of notification to delete.
            context_filter: A dictionary to filter notifications based on their data.
        """
        Notification.objects.filter(
            recipient=recipient,
            notification_type=notification_type,
            data__contains=context_filter,
        ).delete()

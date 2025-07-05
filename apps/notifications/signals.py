# apps/notifications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification


@receiver(post_save, sender=Notification)
def send_in_app_notification(sender, instance, created, **kwargs):
    """
    Sends a real-time notification to the user through Django Channels.
    """
    if created and instance.notification_type.channel == "in_app":
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notifications_{instance.recipient.id}",
            {
                "type": "send_notification",
                "message": instance.message,
            },
        )

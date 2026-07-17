import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatMessage
from apps.users.models import CustomUser
from apps.notifications.services.notification_service import NotificationService


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Deny unauthenticated connections
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.room_name = "chat_room"
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        user = self.scope["user"]
        email = user.email

        # Save message to database using user ID directly
        await self.save_message(user.id, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "email": email},
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event["message"]
        email = event["email"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps({"message": message, "email": email})
        )

        # Send notification to all users except the sender
        await self.send_notifications(email, message)

    @database_sync_to_async
    def save_message(self, user_id, message):
        ChatMessage.objects.create(user_id=user_id, message=message)

    @database_sync_to_async
    def send_notifications(self, sender_email, message):
        try:
            sender = CustomUser.objects.get(email=sender_email)
            recipients = CustomUser.objects.exclude(id=sender.id)
            for recipient in recipients:
                NotificationService.send_notification(
                    recipient=recipient,
                    notification_type="new_chat_message",
                    context={"message": message, "sender": sender_email},
                )
        except CustomUser.DoesNotExist:
            pass

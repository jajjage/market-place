import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatMessage
from apps.users.models import CustomUser
from apps.notifications.services.notification_service import NotificationService


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = "chat_room"
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        username = self.scope["user"].username

        # Save message to database
        await self.save_message(username, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": message, "username": username},
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event["message"]
        username = event["username"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps({"message": message, "username": username})
        )

        # Send notification to all users except the sender
        await self.send_notifications(username, message)

    @database_sync_to_async
    def save_message(self, username, message):
        user = CustomUser.objects.get(username=username)
        ChatMessage.objects.create(user=user, message=message)

    @database_sync_to_async
    def send_notifications(self, sender_username, message):
        sender = CustomUser.objects.get(username=sender_username)
        recipients = CustomUser.objects.exclude(id=sender.id)
        for recipient in recipients:
            NotificationService.send_notification(
                recipient=recipient,
                notification_type="new_chat_message",
                context={"message": message, "sender": sender_username},
            )

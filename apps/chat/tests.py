from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from safetrade.asgi import application
from apps.chat.models import ChatMessage

User = get_user_model()


class ChatConsumerTestCase(TransactionTestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email="user1@test.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            email="user2@test.com", password="password123"
        )

        # Generate access tokens
        self.token1 = str(AccessToken.for_user(self.user1))
        self.token2 = str(AccessToken.for_user(self.user2))

    async def test_connection_without_token_rejected(self):
        communicator = WebsocketCommunicator(application, "ws/chat/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_connection_with_invalid_token_rejected(self):
        communicator = WebsocketCommunicator(
            application, "ws/chat/?token=invalidtokenhere"
        )
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_connection_with_valid_token_accepted(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/?token={self.token1}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_receive_message_saves_to_db_and_broadcasts(self):
        communicator = WebsocketCommunicator(
            application, f"ws/chat/?token={self.token1}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Send a chat message
        await communicator.send_json_to({"message": "Hello World"})

        # Receive broadcast
        response = await communicator.receive_json_from()
        self.assertEqual(response["message"], "Hello World")
        self.assertEqual(response["email"], self.user1.email)

        # Verify message is saved to the database
        @database_sync_to_async
        def get_messages_count():
            return ChatMessage.objects.filter(
                user_id=self.user1.id, message="Hello World"
            ).count()

        count = await get_messages_count()
        self.assertEqual(count, 1)

        await communicator.disconnect()

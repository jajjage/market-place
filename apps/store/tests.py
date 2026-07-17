from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.store.models import UserStore
from apps.store.serializers import UserStoreSerializer

User = get_user_model()


class UserStoreModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="seller@test.com", password="testpass123", first_name="Seller"
        )

    def test_store_slug_generation(self):
        store = UserStore.objects.create(
            user=self.user,
            name="My Epic Store",
            description="Testing slug generation",
        )
        self.assertEqual(store.slug, "my-epic-store")


class UserStoreSerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="seller@test.com", password="testpass123", first_name="Seller"
        )
        class MockRequest:
            user = self.user
        self.mock_request = MockRequest()

    def test_unique_store_validation(self):
        # Create first store
        UserStore.objects.create(
            user=self.user,
            name="First Store",
            slug="first-store",
        )

        # Validate second store creation fails via serializer
        serializer = UserStoreSerializer(
            data={"name": "Second Store"},
            context={"request": self.mock_request}
        )
        with self.assertRaises(serializers.ValidationError):
            serializer.is_valid(raise_exception=True)

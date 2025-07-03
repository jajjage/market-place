from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from apps.comments.models import UserRating
from apps.comments.services import RatingService
from apps.transactions.models import EscrowTransaction


User = get_user_model()


class RatingModelTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@test.com", password="testpass123"
        )
        self.seller = User.objects.create_user(
            email="seller@test.com", password="testpass123"
        )
        self.transaction = EscrowTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            title="Test Product",
            amount=100.00,
            status="completed",
            status_changed_at=timezone.now(),
        )

    def test_rating_creation(self):
        rating = UserRating.objects.create(
            transaction=self.transaction,
            from_user=self.buyer,
            to_user=self.seller,
            rating=5,
            comment="Great seller!",
            is_verified=True,
        )

        self.assertEqual(rating.rating, 5)
        self.assertEqual(rating.from_user, self.buyer)
        self.assertEqual(rating.to_user, self.seller)
        self.assertTrue(rating.is_verified)

    def test_rating_validation(self):
        # Test invalid user roles
        with self.assertRaises(Exception):
            rating = UserRating(
                transaction=self.transaction,
                from_user=self.seller,  # Seller trying to rate
                to_user=self.buyer,
                rating=5,
            )
            rating.clean()


class RatingServiceTest(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@test.com", password="testpass123"
        )
        self.seller = User.objects.create_user(
            email="seller@test.com", password="testpass123"
        )
        self.transaction = EscrowTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            title="Test Product",
            amount=100.00,
            status="completed",
            status_changed_at=timezone.now(),
        )

    def test_rating_eligibility_check(self):
        result = RatingService.check_rating_eligibility(self.transaction.id, self.buyer)
        self.assertTrue(result["can_rate"])
        self.assertEqual(result["seller_name"], self.seller.get_full_name())

    def test_rating_stats_calculation(self):
        # Create some ratings
        for i in range(3):
            UserRating.objects.create(
                transaction=self.transaction,
                from_user=self.buyer,
                to_user=self.seller,
                rating=4 + (i % 2),  # Mix of 4 and 5 star ratings
                is_verified=True,
            )

        stats = RatingService.get_user_rating_stats(self.seller.id, use_cache=False)
        self.assertEqual(stats["total_ratings"], 3)
        self.assertGreater(stats["average_rating"], 4.0)


class RatingAPITest(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            email="buyer@test.com", password="testpass123"
        )
        self.seller = User.objects.create_user(
            email="seller@test.com", password="testpass123"
        )
        self.transaction = EscrowTransaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            title="Test Product",
            amount=100.00,
            status="completed",
            status_changed_at=timezone.now(),
        )

    def test_create_rating(self):
        self.client.force_authenticate(user=self.buyer)

        data = {"rating": 5, "comment": "Excellent service!"}

        response = self.client.post(
            f"/api/ratings/transactions/{self.transaction.id}/rating/", data
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            UserRating.objects.filter(transaction=self.transaction).exists()
        )

    def test_rating_eligibility_check(self):
        self.client.force_authenticate(user=self.buyer)

        response = self.client.get(
            f"/api/ratings/transactions/{self.transaction.id}/rating-eligibility/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["can_rate"])

    def test_unauthorized_rating_creation(self):
        self.client.force_authenticate(user=self.seller)  # Seller trying to rate

        data = {"rating": 5, "comment": "Self rating attempt"}

        response = self.client.post(
            f"/api/ratings/transactions/{self.transaction.id}/rating/", data
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

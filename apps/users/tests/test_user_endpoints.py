import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.users.models.user_rating import UserRating
from apps.users.models.user_store import UserStore
from apps.users.models.user_address import UserAddress
from apps.transactions.models import EscrowTransaction
from apps.products.models import Product, Category, ProductCondition


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user():
    User = get_user_model()
    user = User.objects.create_user(
        email="testuser@example.com",
        password="testpassword123",
        first_name="Test",
        last_name="User",
    )
    return user


@pytest.fixture
def create_transaction(create_user):
    # Create a test transaction
    product = Product.objects.create(
        seller=create_user,
        title="Test Product",
        description="Test description",
        price=100.00,
        currency="USD",
        category=Category.objects.create(name="Test Category"),
        condition=ProductCondition.objects.create(name="New"),
    )

    # Create the transaction with the required product
    return EscrowTransaction.objects.create(
        product=product,
        buyer=create_user,
        seller=create_user,
        amount=100.00,
        currency="USD",
        status="COMPLETED",
        shipping_address={
            "address": "123 Test St",
            "city": "Test City",
            "country": "Test Country",
        },
    )


class TestUserRatingEndpoints:
    @pytest.mark.django_db
    def test_list_ratings(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-rating-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_create_rating(self, api_client, create_user, create_transaction):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-rating-list")
        data = {
            "to_user": create_user.id,
            "rating": 5,
            "comment": "Great user!",
            "transaction": create_transaction.id,
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert UserRating.objects.count() == 1
        assert UserRating.objects.first().rating == 5

    @pytest.mark.django_db
    def test_create_rating_invalid_score(
        self, api_client, create_user, create_transaction
    ):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-rating-list")
        data = {
            "to_user": create_user.id,
            "rating": 6,  # Invalid rating > 5
            "comment": "Invalid rating",
            "transaction": create_transaction.id,
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_create_rating_unauthenticated(
        self, api_client, create_user, create_transaction
    ):
        url = reverse("user-rating-list")
        data = {
            "to_user": create_user.id,
            "rating": 5,
            "comment": "Great user!",
            "transaction": create_transaction.id,
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestUserStoreEndpoints:
    @pytest.mark.django_db
    def test_list_stores(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-store-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_create_store(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-store-list")
        data = {
            "name": "Test Store",
            "description": "Test store description",
            "return_policy": "30 days return",
            "shipping_policy": "Free shipping",
            "website": "https://teststore.com",
            "is_active": True,
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert UserStore.objects.count() == 1
        assert UserStore.objects.first().name == "Test Store"

    @pytest.mark.django_db
    def test_update_store(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        # Create a store first
        store = UserStore.objects.create(
            user=create_user,
            name="Original Store",
            description="Original description",
        )
        url = reverse("user-store-detail", kwargs={"pk": store.pk})
        update_data = {
            "name": "Updated Store",
            "description": "Updated description",
        }
        response = api_client.patch(url, update_data)
        assert response.status_code == status.HTTP_200_OK
        store.refresh_from_db()
        assert store.name == "Updated Store"
        assert store.description == "Updated description"


class TestUserAddressEndpoints:
    @pytest.mark.django_db
    def test_list_addresses(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-address-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.django_db
    def test_create_address(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        url = reverse("user-address-list")
        data = {
            "address_type": "HOME",
            "name": "Home",
            "street_address": "123 Test St",
            "city": "Test City",
            "state": "Test State",
            "postal_code": "12345",
            "country": "Test Country",
            "phone": "1234567890",
            "is_default": True,
        }
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert UserAddress.objects.count() == 1
        assert UserAddress.objects.first().street_address == "123 Test St"

    @pytest.mark.django_db
    def test_update_address(self, api_client, create_user):
        api_client.force_authenticate(user=create_user)
        # Create an address first
        address = UserAddress.objects.create(
            user=create_user,
            address_type="HOME",
            name="Home",
            street_address="123 Old St",
            city="Old City",
            state="Old State",
            postal_code="12345",
            country="Old Country",
            phone="1234567890",
        )
        url = reverse("user-address-detail", kwargs={"pk": address.pk})
        update_data = {
            "street_address": "456 New St",
            "city": "New City",
        }
        response = api_client.patch(url, update_data)
        assert response.status_code == status.HTTP_200_OK
        address.refresh_from_db()
        assert address.street_address == "456 New St"
        assert address.city == "New City"

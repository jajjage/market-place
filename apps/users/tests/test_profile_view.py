import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model


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
        user_type="SELLER",
    )
    return user


@pytest.mark.django_db
def test_retrieve_user_profile(api_client, create_user):
    """Test retrieving user profile"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == create_user.email
    assert response.data["first_name"] == create_user.first_name
    assert response.data["last_name"] == create_user.last_name


@pytest.mark.django_db
def test_update_user_profile(api_client, create_user):
    """Test updating user profile"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {
        "first_name": "Updated",
        "last_name": "Name",
        "profile": {
            "bio": "Test bio",
            "phone_number": "+1234567890",
            "notification_email": True,
            "notification_sms": True,
        },
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Updated"
    assert response.data["last_name"] == "Name"
    assert response.data["profile"]["bio"] == "Test bio"
    assert response.data["profile"]["phone_number"] == "+1234567890"


@pytest.mark.django_db
def test_update_user_profile_invalid_data(api_client, create_user):
    """Test updating user profile with invalid data"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "invalid-email",  # Invalid email format
        "profile": {"phone_number": "invalid"},  # Invalid phone format
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_user_profile_unauthorized(api_client, create_user):
    """Test accessing profile without authentication"""
    url = reverse("user-me")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_user_profile_patch_allowed(api_client, create_user):
    """Test full profile update with PUT method"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {
        "first_name": "Complete",
        "last_name": "Update",
        "profile": {
            "bio": "Complete profile update",
            "phone_number": "+1987654321",
            "notification_email": False,
            "notification_sms": False,
        },
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Complete"
    assert response.data["last_name"] == "Update"
    assert response.data["profile"]["bio"] == "Complete profile update"


@pytest.mark.django_db
def test_user_profile_with_address(api_client, create_user):
    """Test profile update with address"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {
        "addresses": [
            {
                "address_type": "shipping",
                "name": "Home",
                "street_address": "123 Test St",
                "city": "Test City",
                "state": "Test State",
                "postal_code": "12345",
                "country": "Test Country",
                "phone": "1234567890",
            }
        ]
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["addresses"]) == 1
    assert response.data["addresses"][0]["street_address"] == "123 Test St"


@pytest.mark.django_db
def test_user_profile_verification_status(api_client, create_user):
    """Test profile verification status display"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert "verification_status" in response.data


@pytest.mark.django_db
def test_user_profile_list(api_client, create_user):
    """Test listing all user profiles"""
    api_client.force_authenticate(user=create_user)
    url = reverse("user-profile-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) > 0


@pytest.mark.django_db
def test_user_profile_full_data(api_client, create_user):
    """Test retrieving full profile data including ratings and store"""
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)

    # Create a store for the user
    store_url = reverse("user-store-list")
    store_data = {
        "name": "Test Store",
        "description": "Test store description",
        "is_active": False,
    }
    api_client.post(store_url, store_data)

    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert "email" in response.data
    assert "store" in response.data
    assert response.data["store"]["name"] == "Test Store"

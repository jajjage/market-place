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
        email="testuser@example.com", password="testpassword"
    )
    return user


@pytest.mark.django_db
def test_retrieve_user_profile(api_client, create_user):
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == create_user.email
    assert "first_name" in response.data
    assert "last_name" in response.data
    assert "user_type" in response.data
    assert "verification_status" in response.data
    assert "profile" in response.data
    assert "verification_status" in response.data


@pytest.mark.django_db
def test_update_user_profile(api_client, create_user):
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)

    data = {
        "first_name": "NewFirstName",
        "last_name": "NewLastName",
        "user_type": "BUYER",
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    create_user.refresh_from_db()
    assert create_user.first_name == "NewFirstName"
    assert create_user.last_name == "NewLastName"
    assert create_user.user_type == "BUYER"


@pytest.mark.django_db
def test_update_user_profile_invalid_data(api_client, create_user):
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {"email": "not-an-email"}
    response = api_client.put(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_user_profile_unauthorized(api_client):
    url = reverse("user-me")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# i MAY ENABLE THE DELETE LATTER
# @pytest.mark.django_db
# def test_delete_user_profile(api_client, create_user):
#     url = reverse("user-me")
#     api_client.force_authenticate(user=create_user)
#     response = api_client.delete(url)
#     assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_user_profile_put_allowed(api_client, create_user):
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "updateduser@example.com",
        "first_name": "UpdatedFirstName",
        "last_name": "UpdatedLastName",
        "user_type": "SELLER",
        "verification_status": "VERIFIED",
        "profile": {},
    }
    response = api_client.put(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    create_user.refresh_from_db()
    assert create_user.first_name == "UpdatedFirstName"
    assert create_user.last_name == "UpdatedLastName"
    assert create_user.user_type == "SELLER"


@pytest.mark.django_db
def test_user_profile_patch_allowed(api_client, create_user):
    url = reverse("user-me")
    api_client.force_authenticate(user=create_user)
    data = {
        "first_name": "UpdatedFirstName",
        "last_name": "UpdatedLastName",
        "user_type": "ADMIN",
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    create_user.refresh_from_db()
    assert create_user.first_name == "UpdatedFirstName"
    assert create_user.last_name == "UpdatedLastName"

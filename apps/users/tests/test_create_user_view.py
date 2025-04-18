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
def test_create_user_success(api_client, create_user):
    url = reverse("user-list")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "newuser@example.com",
        "first_name": "Test",
        "last_name": "User",
        "user_type": "BUYER",
        "password": "StrongTestPass123!",
        "re_password": "StrongTestPass123!",
    }
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert get_user_model().objects.filter(email="newuser@example.com").exists()


@pytest.mark.django_db
def test_create_user_missing_fields(api_client, create_user):
    url = reverse("user-list")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "newuser@example.com"
        # Missing password and password2
    }
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_user_invalid_data(api_client, create_user):
    url = reverse("user-list")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "not-an-email@mail.com",
        "first_name": "Test",
        "last_name": "User",
        "user_type": "buyer",  # Invalid user type
        "password": "newpassword",
        "re_password": "newpassword",
    }
    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_user_put_not_allowed(api_client, create_user):
    url = reverse("user-list")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "newuser@example.com",
        "first_name": "Test",
        "last_name": "User",
        "user_type": "BUYER",
        "password": "newpassword",
        "re_password": "newpassword",
    }
    response = api_client.put(url, data, format="json")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_create_user_patch_not_allowed(api_client, create_user):
    url = reverse("user-list")
    api_client.force_authenticate(user=create_user)
    data = {
        "email": "newuser@example.com",
        "first_name": "Test",
        "last_name": "User",
        "user_type": "BUYER",
        "password": "newpassword",
        "re_password": "newpassword",
    }
    response = api_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_create_user_delete_not_allowed(api_client, create_user):
    url = reverse("user-list")
    api_client.force_authenticate(user=create_user)
    response = api_client.delete(url)
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

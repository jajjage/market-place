import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework import status


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user():
    User = get_user_model()
    user = User.objects.create_user(
        email="testuser@example.com", password="old_password"
    )
    return user


@pytest.mark.django_db
def test_set_password_authenticated(api_client, create_user):
    """Test setting a new password when authenticated."""
    api_client.force_authenticate(user=create_user)
    old_password = (
        "old_password"  # Assuming this is the password from create_user fixture
    )

    # Set the password for the test user if needed
    create_user.set_password(old_password)
    create_user.save()

    url = reverse("customuser-set-password")
    data = {
        "current_password": old_password,
        "new_password": "newSecurePassword123!",
        "re_new_password": "newSecurePassword123!",
    }

    response = api_client.post(url, data, format="json")
    # Your API returns 204 No Content, not 200 OK
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify the password was actually changed
    create_user.refresh_from_db()
    assert create_user.check_password("newSecurePassword123!")


@pytest.mark.django_db
def test_set_password_unauthenticated(api_client):
    """Test setting a password without authentication."""
    url = reverse("customuser-set-password")
    data = {
        "current_password": "old_password",
        "new_password": "newSecurePassword123!",
        "re_new_password": "newSecurePassword123!",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_set_password_wrong_current_password(api_client, create_user):
    """Test setting a password with wrong current password."""
    api_client.force_authenticate(user=create_user)

    # Set a known password
    create_user.set_password("correct_password")
    create_user.save()

    url = reverse("customuser-set-password")
    data = {
        "current_password": "wrongpassword",
        "new_password": "newSecurePassword123!",
        "re_new_password": "newSecurePassword123!",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Verify the password was not changed
    create_user.refresh_from_db()
    assert not create_user.check_password("newSecurePassword123!")
    assert create_user.check_password("correct_password")


@pytest.mark.django_db
def test_set_password_password_mismatch(api_client, create_user):
    """Test setting a password with mismatched new passwords."""
    api_client.force_authenticate(user=create_user)

    # Set a known password
    create_user.set_password("current_password")
    create_user.save()

    url = reverse("customuser-set-password")
    data = {
        "current_password": "current_password",
        "new_password": "newSecurePassword123!",
        "re_new_password": "differentPassword123!",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Verify the password was not changed
    create_user.refresh_from_db()
    assert not create_user.check_password("newSecurePassword123!")
    assert create_user.check_password("current_password")


@pytest.mark.django_db
def test_set_password_weak_password(api_client, create_user):
    """Test setting a weak password that doesn't meet requirements."""
    api_client.force_authenticate(user=create_user)

    # Set a known password
    create_user.set_password("current_password")
    create_user.save()

    url = reverse("customuser-set-password")
    data = {
        "current_password": "current_password",
        "new_password": "weak",  # Too short/simple
        "re_new_password": "weak",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Verify the password was not changed
    create_user.refresh_from_db()
    assert not create_user.check_password("weak")
    assert create_user.check_password("current_password")

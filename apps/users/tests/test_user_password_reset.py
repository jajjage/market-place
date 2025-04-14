import pytest
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
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
        email="testuser@example.com", password="testpassword"
    )
    return user


@pytest.mark.django_db
def test_reset_password_request(api_client, create_user):
    """Test requesting a password reset email."""
    url = reverse("customuser-reset-password")
    data = {"email": create_user.email}

    # Directly call the endpoint without mocking
    response = api_client.post(url, data, format="json")

    # Assert the response is successful
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_reset_password_request_invalid_email(api_client):
    """Test requesting a password reset with an invalid email."""
    url = reverse("customuser-reset-password")
    data = {"email": "nonexistent@example.com"}

    response = api_client.post(url, data, format="json")

    # Even with invalid email, the API should still return 204 for security
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_reset_password_confirm(api_client, create_user):
    """Test confirming a password reset with token."""
    # Generate the token and uid that would be sent in the email
    uid = urlsafe_base64_encode(force_bytes(create_user.pk))
    token = default_token_generator.make_token(create_user)

    url = reverse("customuser-reset-password-confirm")
    data = {
        "uid": uid,
        "token": token,
        "new_password": "newSecurePassword123!",
        "re_new_password": "newSecurePassword123!",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify the password was actually changed
    create_user.refresh_from_db()
    assert create_user.check_password("newSecurePassword123!")


@pytest.mark.django_db
def test_reset_password_confirm_invalid_token(api_client, create_user):
    """Test confirming a password reset with an invalid token."""
    uid = urlsafe_base64_encode(force_bytes(create_user.pk))

    url = reverse("customuser-reset-password-confirm")
    data = {
        "uid": uid,
        "token": "invalid-token",
        "new_password": "newSecurePassword123!",
        "re_new_password": "newSecurePassword123!",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Verify the password was not changed
    create_user.refresh_from_db()
    assert not create_user.check_password("newSecurePassword123!")


@pytest.mark.django_db
def test_reset_password_confirm_password_mismatch(api_client, create_user):
    """Test confirming a password reset with mismatched passwords."""
    uid = urlsafe_base64_encode(force_bytes(create_user.pk))
    token = default_token_generator.make_token(create_user)

    url = reverse("customuser-reset-password-confirm")
    data = {
        "uid": uid,
        "token": token,
        "new_password": "newSecurePassword123!",
        "re_new_password": "differentPassword123!",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Verify the password was not changed
    create_user.refresh_from_db()
    assert not create_user.check_password("newSecurePassword123!")

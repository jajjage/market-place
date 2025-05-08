import pytest
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch
from django.core.cache import cache

User = get_user_model()


@pytest.fixture
def user_data():
    return {
        "email": "testuser@test.com",
        "first_name": "Test",
        "last_name": "User",
        "user_type": "BUYER",
        "password": "StrongTestPass123!",
        "re_password": "StrongTestPass123!",
    }


@pytest.fixture
def create_user(user_data):
    user = User.objects.create_user(
        email=user_data["email"],
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        user_type=user_data["user_type"],
        password=user_data["password"],
        is_active=True,
    )
    return user


@pytest.fixture
def inactive_user(user_data):
    user = User.objects.create_user(
        email="inactive@example.com",
        first_name="Inactive",
        last_name="User",
        user_type="BUYER",
        password=user_data["password"],
        is_active=False,
    )
    return user


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, create_user, user_data):
    url = reverse("token_obtain_pair")
    response = api_client.post(url, user_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    return api_client


@pytest.mark.django_db
class TestCookieTokenObtainPairView:
    def test_login_success(self, api_client, user_data, create_user):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, user_data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # grab the inner payload
        payload = response.data["data"]

        # now you can run your assertions against payload
        assert "email" in payload
        assert "user_type" in payload
        assert "verification_status" in payload
        assert "first_name" in payload
        assert "last_name" in payload

        assert payload["email"] == "testuser@test.com"
        assert payload["user_type"] is not None
        assert payload["verification_status"] is not None

        # and make sure you didn't accidentally leak the raw tokens
        assert "access" not in response.data
        assert "refresh" not in response.data

    def test_login_invalid_credentials(self, api_client, user_data):
        url = reverse("token_obtain_pair")
        invalid_data = user_data.copy()
        invalid_data["password"] = "WrongPassword123!"

        response = api_client.post(url, invalid_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert settings.JWT_AUTH_COOKIE not in response.cookies
        assert settings.JWT_AUTH_REFRESH_COOKIE not in response.cookies

    def test_login_inactive_user(self, api_client, user_data, inactive_user):
        url = reverse("token_obtain_pair")
        inactive_data = {
            "email": "inactive@example.com",
            "password": user_data["password"],
        }

        response = api_client.post(url, inactive_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert settings.JWT_AUTH_COOKIE not in response.cookies
        assert settings.JWT_AUTH_REFRESH_COOKIE not in response.cookies

    @patch("apps.users.views.TokenObtainPairView.post")
    def test_login_token_error(self, mock_post, api_client, user_data):
        from rest_framework_simplejwt.exceptions import TokenError

        mock_post.side_effect = TokenError("Token generation failed")
        url = reverse("token_obtain_pair")

        response = api_client.post(url, user_data, format="json")

        print(response.data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "Authentication failed"

    @patch("apps.users.views.update_last_login")
    def test_login_updates_last_login(
        self, mock_update_last_login, api_client, user_data, create_user
    ):
        url = reverse("token_obtain_pair")
        response = api_client.post(url, user_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        mock_update_last_login.assert_called_once()


@pytest.mark.django_db
class TestCookieTokenRefreshView:
    def test_refresh_success(self, authenticated_client):
        # Get the refresh token from cookies
        refresh_token = authenticated_client.cookies[
            settings.JWT_AUTH_REFRESH_COOKIE
        ].value

        # Clear cookies to simulate a new request
        authenticated_client.cookies.clear()

        # Manually set the refresh token
        authenticated_client.cookies[settings.JWT_AUTH_REFRESH_COOKIE] = refresh_token

        url = reverse("token_refresh")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert settings.JWT_AUTH_COOKIE in response.cookies
        assert "access" not in response.data

    def test_refresh_no_token(self, api_client):
        url = reverse("token_refresh")
        response = api_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "No refresh token found"

    def test_refresh_blacklisted_token(self, authenticated_client):
        refresh_token = authenticated_client.cookies[
            settings.JWT_AUTH_REFRESH_COOKIE
        ].value
        authenticated_client.cookies.clear()
        authenticated_client.cookies[settings.JWT_AUTH_REFRESH_COOKIE] = refresh_token

        # Blacklist the token
        cache.set(f"blacklist_token_{refresh_token}", True, 300)

        url = reverse("token_refresh")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "Token is blacklisted"

        # Clean up
        cache.delete(f"blacklist_token_{refresh_token}")

    def test_refresh_rate_limit(self, authenticated_client):
        refresh_token = authenticated_client.cookies[
            settings.JWT_AUTH_REFRESH_COOKIE
        ].value
        authenticated_client.cookies.clear()
        authenticated_client.cookies[settings.JWT_AUTH_REFRESH_COOKIE] = refresh_token

        # Set the rate limit
        cache.set(f"refresh_attempt_{refresh_token}", 5, 300)

        url = reverse("token_refresh")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.data["message"] == "Too many refresh attempts"

        # Clean up
        cache.delete(f"refresh_attempt_{refresh_token}")

    @patch("rest_framework_simplejwt.views.TokenRefreshView.post")
    def test_refresh_token_error(self, mock_post, authenticated_client):
        from rest_framework_simplejwt.exceptions import TokenError

        mock_post.side_effect = TokenError("Invalid token")
        refresh_token = authenticated_client.cookies[
            settings.JWT_AUTH_REFRESH_COOKIE
        ].value
        authenticated_client.cookies.clear()
        authenticated_client.cookies[settings.JWT_AUTH_REFRESH_COOKIE] = refresh_token

        url = reverse("token_refresh")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "Invalid token"


@pytest.mark.django_db
class TestCookieTokenVerifyView:
    def test_verify_success(self, authenticated_client):
        url = reverse("token_verify")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK

    def test_verify_no_token(self, api_client):
        url = reverse("token_verify")
        response = api_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "No token found"

    @patch("rest_framework_simplejwt.views.TokenVerifyView.post")
    def test_verify_invalid_token(self, mock_post, authenticated_client):
        from rest_framework_simplejwt.exceptions import InvalidToken

        mock_post.side_effect = InvalidToken("Invalid token")
        url = reverse("token_verify")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["message"] == "Invalid token"


@pytest.mark.django_db
class TestLogoutView:
    def test_logout_success(self, authenticated_client):
        url = reverse("auth_logout")
        response = authenticated_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Successfully logged out."

        # Check cookies are deleted
        assert (
            settings.JWT_AUTH_COOKIE not in response.cookies
            or not response.cookies[settings.JWT_AUTH_COOKIE].value
        )
        assert (
            settings.JWT_AUTH_REFRESH_COOKIE not in response.cookies
            or not response.cookies[settings.JWT_AUTH_REFRESH_COOKIE].value
        )

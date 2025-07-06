import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from jsonschema import ValidationError
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.auth.traditional.serializers import LogoutSerializer
from apps.core.views import BaseAPIView

from apps.auth.traditional.throttles import UserLoginRateThrottle
from apps.core.utils.cookie_set import CookieSet
from .schema import (
    # login_schema,
    refresh_schema,
    verify_schema,
    logout_schema,
    test_auth_schema,
)


logger = logging.getLogger(__name__)

User = get_user_model()


# @login_schema
class CookieTokenObtainPairView(TokenObtainPairView, CookieSet, BaseAPIView):
    """
    Custom view to obtain token pairs with cookie support.
    Extends TokenObtainPairView and sets tokens in cookies on successful authentication.
    """

    throttle_classes = [UserLoginRateThrottle]

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to obtain token pair.
        Sets token cookies and updates last login on success.
        """
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == status.HTTP_200_OK:
                user = self.get_user(request)
                if user:
                    update_last_login(None, user)
                    response = self.set_token_cookies(response)
                    # Modify response data instead of creating new response
                    response.data = {
                        "status": "success",
                        "message": "Login successful",
                        "data": response.data,
                    }

                    return response
            return response
        except (TokenError, ValidationError) as e:
            logger.exception("Token generation failed: %s", e)
            return self.error_response(
                data=str(e),
                message="Authentication failed",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    def get_user(self, request):
        """
        Retrieve the user object from the validated serializer data.

        Args:
            request (Request): The request object containing user credentials.

        Returns:
            User instance.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.user


@refresh_schema
class CookieTokenRefreshView(TokenRefreshView, CookieSet, BaseAPIView):
    """
    Custom TokenRefreshView to handle refresh tokens in cookies.
    Handles rate limiting and blacklist checks for refresh tokens.
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to refresh tokens using the refresh token from cookies.
        Applies rate limiting and blacklist checks.
        """
        refresh_token = request.COOKIES.get(settings.JWT_AUTH_REFRESH_COOKIE)

        if not refresh_token:
            return self.error_response(
                message="No refresh token found",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        if self._is_token_blacklisted(refresh_token):
            return self.error_response(
                message="Token is blacklisted", status_code=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Rate limiting check
            if not self._check_rate_limit(refresh_token):
                return self.error_response(
                    message="Too many refresh attempts",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Validate and get new tokens
            request._full_data = {"refresh": refresh_token}
            response = super().post(request, *args, **kwargs)

            if response.status_code == status.HTTP_200_OK:
                response = self.set_token_cookies(response)
                # Update response data instead of creating new response
                response.data = {
                    "status": "success",
                    "message": "Token refreshed successfully",
                    "data": response.data,
                }
                return response

        except TokenError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error("Token refresh error: %s", e, exc_info=True)  # noqa: G201
            return self.error_response(
                message="Token refresh failed",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _is_token_blacklisted(self, token, cache_timeout=300):
        """
        Check if a token is blacklisted using cache.

        Args:
            token (str): The token to check.
            cache_timeout (int): Cache timeout in seconds.

        Returns:
            bool: True if token is blacklisted, False otherwise.
        """
        cache_key = f"blacklist_token_{token}"
        return cache.get(cache_key, False)

    def _check_rate_limit(self, token, max_attempts=5, timeout=300):
        """
        Check and increment the rate limit for token refresh attempts.

        Args:
            token (str): The token to check.
            max_attempts (int): Maximum allowed attempts.
            timeout (int): Cache timeout in seconds.

        Returns:
            bool: True if under rate limit, False otherwise.
        """
        cache_key = f"refresh_attempt_{token}"
        attempts = cache.get(cache_key, 0)

        if attempts >= max_attempts:
            return False

        cache.set(cache_key, attempts + 1, timeout)
        return True


@verify_schema
class CookieTokenVerifyView(TokenVerifyView, BaseAPIView):
    """
    Verifies the access token from the cookie.
    """

    def post(self, request, *args, **kwargs):
        """
        Handles the POST request to verify the token.
        """
        token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)

        if not token:
            return self.error_response(
                message="No token found", status_code=status.HTTP_401_UNAUTHORIZED
            )

        try:
            request.data["token"] = token
            response = super().post(request, *args, **kwargs)
            return self.success_response(
                data=response.data,
                message="Token verified successfully",
                status_code=status.HTTP_200_OK,
            )
        except InvalidToken as e:
            logger.exception("Token verification error: %s", e)
            return self.error_response(
                message="Invalid token", status_code=status.HTTP_401_UNAUTHORIZED
            )


@logout_schema
class LogoutView(BaseAPIView):
    """
    Logs out the user by clearing the authentication cookies.
    """

    serializer_class = LogoutSerializer

    def post(self, request, *args, **kwargs):
        """
        Handles the POST request to log out the user.
        """
        try:
            response = self.success_response(
                message="Successfully logged out.", status_code=status.HTTP_200_OK
            )
            response.delete_cookie(settings.JWT_AUTH_COOKIE)
            response.delete_cookie(settings.JWT_AUTH_REFRESH_COOKIE)
            return response
        except Exception as e:
            logger.error("Logout error: %s", e, exc_info=True)
            return self.error_response(
                message="Logout failed", status_code=status.HTTP_400_BAD_REQUEST
            )


@test_auth_schema
class TestAuthView(BaseAPIView):
    """
    A view to test if the user is authenticated.
    """

    def get(self, request, *args, **kwargs):
        """
        Handles the GET request to test authentication.
        """
        return self.success_response(
            message="You are authenticated", status_code=status.HTTP_200_OK
        )

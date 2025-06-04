import logging
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status


logger = logging.getLogger(__name__)


class CookieSet:
    """Class to manage setting cookies for authentication tokens."""

    def set_token_cookies(self, response):
        try:
            logger.debug("Setting authentication cookies")
            self._validate_token_data(response.data)

            # Set access token cookie
            response.set_cookie(
                settings.JWT_AUTH_COOKIE,
                response.data["access"],
                max_age=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds(),
                secure=settings.JWT_AUTH_SECURE,
                httponly=settings.JWT_AUTH_HTTPONLY,
                samesite=settings.JWT_AUTH_SAMESITE,
                path=settings.JWT_AUTH_PATH,
            )

            # Set refresh token cookie
            response.set_cookie(
                settings.JWT_AUTH_REFRESH_COOKIE,
                response.data["refresh"],
                max_age=settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds(),
                secure=settings.JWT_AUTH_SECURE,
                httponly=settings.JWT_AUTH_HTTPONLY,
                samesite=settings.JWT_AUTH_SAMESITE,
                path=settings.JWT_AUTH_PATH,
            )

            # Remove tokens from response data for security
            response.data.pop("access")
            response.data.pop("refresh")
            logger.info("Authentication cookies set successfully")
            return response

        except Exception as e:
            logger.exception("Failed to set cookies: %s", e)
            return Response(
                {"error": "Failed to set authentication cookies"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _validate_token_data(self, data):
        """Validate that both access and refresh tokens are present."""
        if not isinstance(data, dict):
            raise ValueError("Response data must be a dictionary")

        if "access" not in data or "refresh" not in data:
            raise ValueError("Both access and refresh tokens are required")

        if not data["access"] or not data["refresh"]:
            raise ValueError("Token values cannot be empty")

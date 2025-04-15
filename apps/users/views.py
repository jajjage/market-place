import logging

from django.conf import settings
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema
from django.contrib.auth.models import update_last_login
from django.core.cache import cache
from jsonschema import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from apps.users.signals import user_activated_signal
from djoser.views import UserViewSet
from djoser.social.views import ProviderAuthView
from djoser import signals
from apps.users.utils import CookieSet

from apps.users.schema import (
    LOGIN_RESPONSE_SCHEMA,
    LOGOUT_SCHEMA,
    TOKEN_REFRESH_SCHEMA,
    TOKEN_VERIFY_SCHEMA,
    USER_ACTIVATION_SCHEMA,
)

logger = logging.getLogger(__name__)


class CustomSocialProviderView(ProviderAuthView, CookieSet):
    """
    Custom social provider view to handle authentication with social providers.
    Extends ProviderAuthView and adds cookie support for tokens.
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST request for social authentication.
        Sets token cookies if authentication is successful.
        """
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == status.HTTP_201_CREATED:
                user = self.get_user(response)
                if user:
                    update_last_login(None, user)
                    self.set_token_cookies(response)
            return response
        except (TokenError, ValidationError) as e:
            logger.exception("Token generation failed: %s", e)
            return Response(
                {"error": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED
            )

    def get_user(self, response):
        """
        Retrieve the user object from the validated token or serializer data.

        Args:
            response (Response): The response object containing user data.

        Returns:
            User instance or None if not found.
        """
        user_email = response.data.get("user", {})

        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            user = None

        return user


@extend_schema(responses=LOGIN_RESPONSE_SCHEMA)
class CookieTokenObtainPairView(TokenObtainPairView, CookieSet):
    """
    Custom view to obtain token pairs with cookie support.
    Extends TokenObtainPairView and sets tokens in cookies on successful authentication.
    """

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
                    return self.set_token_cookies(response)
            return response
        except (TokenError, ValidationError) as e:
            logger.exception("Token generation failed: %s", e)
            return Response(
                {"error": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED
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


@extend_schema(responses=TOKEN_REFRESH_SCHEMA)
class CookieTokenRefreshView(TokenRefreshView, CookieSet):
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
            return Response(
                {"detail": "No refresh token found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if self._is_token_blacklisted(refresh_token):
            return Response(
                {"detail": "Token is blacklisted"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Rate limiting check
            if not self._check_rate_limit(refresh_token):
                return Response(
                    {"detail": "Too many refresh attempts"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            # Validate and get new tokens
            request._full_data = {"refresh": refresh_token}
            response = super().post(request, *args, **kwargs)

            if response.status_code == status.HTTP_200_OK:
                self._set_token_cookies(response)
                return response

        except TokenError as e:
            return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error("Token refresh error: %s", e, exc_info=True)  # noqa: G201
            return Response(
                {"detail": "Token refresh failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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


@extend_schema(responses=TOKEN_VERIFY_SCHEMA)
class CookieTokenVerifyView(TokenVerifyView):
    """
    Custom TokenVerifyView to verify JWT tokens from cookies.
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to verify the JWT token from cookies.

        Args:
            request (Request): The request object.

        Returns:
            Response: Verification result.
        """
        token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)

        if not token:
            return Response(
                {"error": "No token found"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            request.data["token"] = token
            return super().post(request, *args, **kwargs)
        except InvalidToken as e:
            logger.exception("Token verification error: %s", e)
            return Response(
                {"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED
            )


@extend_schema(responses=LOGOUT_SCHEMA)
class LogoutView(APIView):
    """
    API view to handle user logout by deleting authentication cookies.
    """

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to log out the user and delete authentication cookies.

        Args:
            request (Request): The request object.

        Returns:
            Response: Logout result.
        """
        try:
            response = Response({"detail": "Successfully logged out."})
            response.delete_cookie(settings.JWT_AUTH_COOKIE)
            response.delete_cookie(settings.JWT_AUTH_REFRESH_COOKIE)
            return response
        except Exception as e:
            logger.error("Logout error: %s", e, exc_info=True)  # noqa: G201
            return Response(
                {"error": "Logout failed"}, status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(responses=USER_ACTIVATION_SCHEMA)
class CustomUserViewSet(UserViewSet):
    """
    Custom user viewset to handle user activation and other user-related actions.
    Extends Djoser's UserViewSet.
    """

    def get_serializer_class(self):
        """
        Return the serializer class to be used for the request.
        """
        return super().get_serializer_class()

    @action(["post"], detail=False)
    def activation(self, request, *args, **kwargs):
        """
        Activate a user account if not already activated or verified.

        Args:
            request (Request): The request object.

        Returns:
            Response: Activation result.
        """
        # Check if the user is already activated
        if request.user.is_active:
            return Response(
                {"detail": "User is already activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Check if the user is already verified
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        user.is_active = True

        # Add your custom verification status update here
        user.verification_status = "VERIFIED"  # Adjust based on your field's choices
        if user.user_type == "ADMIN":
            user.is_staff = True

        user.save()

        signals.user_activated.send(
            sender=self.__class__, user=user, request=self.request
        )

        # Fire your custom signal
        user_activated_signal.send(sender=self.__class__, user=user)

        # if settings.SEND_CONFIRMATION_EMAIL:
        #     context = {"user": user}
        #     to = [get_user_email(user)]
        #     settings.EMAIL.confirmation(self.request, context).send(to)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["post"], detail=False)
    def reset_email(self, request, *args, **kwargs):
        """
        Disallow resetting email via this endpoint.

        Args:
            request (Request): The request object.

        Returns:
            Response: Method not allowed.
        """
        return Response(
            {"detail": "Not allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @action(["post"], detail=False)
    def set_email(self, request, *args, **kwargs):
        """
        Disallow setting email via this endpoint.

        Args:
            request (Request): The request object.

        Returns:
            Response: Method not allowed.
        """
        return Response(
            {"detail": "Not allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

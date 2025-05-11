import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
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

from djoser.social.views import ProviderAuthView
from apps.core.permissions import IsOwnerOrReadOnly, UserTypePermission
from apps.core.views import BaseAPIView, BaseViewSet
from rest_framework import viewsets, permissions

from apps.users.models.base import CustomUser
from apps.users.utils import CookieSet

from apps.users.schema import (
    LOGIN_RESPONSE_SCHEMA,
    LOGOUT_SCHEMA,
    TOKEN_REFRESH_SCHEMA,
    TOKEN_VERIFY_SCHEMA,
)
from apps.users.serializers import (
    PublicUserSerializer,
    UserRatingSerializer,
    UserStoreSerializer,
    UserAddressSerializer,
)
from apps.users.models.user_rating import UserRating
from apps.users.models.user_store import UserStore
from apps.users.models.user_address import UserAddress

logger = logging.getLogger(__name__)

User = get_user_model()


class CustomSocialProviderView(ProviderAuthView, CookieSet, BaseAPIView):
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
            logger.info(f"Initial response data: {response.data}")

            if response.status_code == status.HTTP_201_CREATED:
                # Get the user's email from the response data
                user_email = response.data.get("user")
                logger.info(f"Found user email: {user_email}")

                if user_email:
                    from django.contrib.auth import get_user_model

                    User = get_user_model()
                    try:
                        user = User.objects.get(email=user_email)
                        update_last_login(None, user)

                        tokens = {
                            "access": response.data.get("access"),
                            "refresh": response.data.get("refresh"),
                        }

                        # Update user data
                        user_data = {
                            "id": str(user.id),
                            "email": user.email,
                            "first_name": user.first_name,
                            "last_name": user.last_name,
                            "user_type": (
                                user.user_type
                                if user.user_type not in ["undefined", None, ""]
                                else None
                            ),
                            "verification_status": (
                                user.verification_status
                                if hasattr(user, "verification_status")
                                else None
                            ),
                        }

                        # Add profile data if user has an associated profile
                        if hasattr(user, "profile"):
                            profile = user.profile
                            profile_data = {
                                "id": str(profile.id),
                                "display_name": profile.display_name,
                                "bio": profile.bio,
                                "phone_number": profile.phone_number,
                                "country": profile.country,
                                "city": profile.city,
                                "email_verified": profile.email_verified,
                                "phone_verified": profile.phone_verified,
                            }

                            if profile.avatar_url:
                                profile_data["avatar_url"] = profile.avatar_url
                            else:
                                profile_data["avatar_url"] = None

                            user_data["profile"] = profile_data

                        # Set tokens and cookies
                        response.data.update(tokens)
                        response = self.set_token_cookies(response)

                        # Update response data instead of creating new response
                        response.data = {
                            "status": "success",
                            "message": "Social authentication successful",
                            "data": user_data,
                        }
                        return response

                    except User.DoesNotExist:
                        logger.error(f"User with email {user_email} not found")
                        return self.error_response(
                            message="User not found",
                            status_code=status.HTTP_404_NOT_FOUND,
                        )

            return response
        except (TokenError, ValidationError) as e:
            logger.exception("Token generation failed: %s", e)
            return self.error_response(
                message="Authentication failed",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )


@extend_schema(responses=LOGIN_RESPONSE_SCHEMA)
class CookieTokenObtainPairView(TokenObtainPairView, CookieSet, BaseAPIView):
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


@extend_schema(responses=TOKEN_REFRESH_SCHEMA)
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


@extend_schema(responses=TOKEN_VERIFY_SCHEMA)
class CookieTokenVerifyView(TokenVerifyView, BaseAPIView):
    def post(self, request, *args, **kwargs):
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


@extend_schema(responses=LOGOUT_SCHEMA)
class LogoutView(BaseAPIView):
    def post(self, request, *args, **kwargs):
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


@extend_schema(tags=["User Ratings"])
class UserRatingViewSet(BaseViewSet):
    queryset = UserRating.objects.all()
    serializer_class = UserRatingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        return UserRating.objects.filter(to_user=user) | UserRating.objects.filter(
            from_user=user
        )

    def perform_create(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(from_user=self.request.user)

    def perform_update(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(from_user=self.request.user)


@extend_schema(tags=["User Store"])
class UserStoreViewSet(BaseViewSet):
    queryset = UserStore.objects.all()
    serializer_class = UserStoreSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        return UserStore.objects.filter(user=user)

    def perform_create(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(user=self.request.user)


@extend_schema(tags=["User Address"])
class UserAddressViewSet(BaseViewSet):
    queryset = UserAddress.objects.all()
    serializer_class = UserAddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        return UserAddress.objects.filter(user=user)

    def perform_create(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(user=self.request.user)


@extend_schema(tags=["User Profile"])
class UserProfileViewSet(viewsets.ReadOnlyModelViewSet, BaseViewSet):
    serializer_class = PublicUserSerializer
    permission_classes = [UserTypePermission]
    permission_user_types = ["SELLER", "BUYER"]

    def get_queryset(self):
        return CustomUser.objects.select_related("profile").filter(
            profile__isnull=False
        )

    def perform_create(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """Set the seller to the current user when creating a product"""
        serializer.save(user=self.request.user)

    def get_object(self):
        if self.kwargs.get("pk") == "me":
            return self.request.user
        return super().get_object()

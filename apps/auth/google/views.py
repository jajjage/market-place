import logging
from urllib.parse import quote_plus

from django.shortcuts import redirect
from jsonschema import ValidationError
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth.models import update_last_login
from djoser.social.views import ProviderAuthView
from apps.core.views import BaseAPIView

from apps.core.utils.cookie_set import CookieSet

logger = logging.getLogger(__name__)


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

    def get(self, request, provider):
        redirect_uri = request.GET.get("redirect_uri")

        if not redirect_uri:
            return self.error_response(
                message="redirect_uri query parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Build your Djoser/social-auth-app-django social login URL here
        # This is the crucial part that generates the initial redirect to Google
        # For Djoser, this might involve constructing a URL like:
        # f"/o/{provider}/?redirect_uri={quote_plus(redirect_uri)}"
        # Or you might be using a backend library that generates this URL for you.

        # Example: if you're directly redirecting to a social-auth-app-django URL
        # Make sure the redirect_uri passed to the Djoser endpoint is itself encoded
        djoser_social_auth_url = f"http://localhost:8000/o/{provider}/?redirect_uri={quote_plus(redirect_uri)}"

        # Redirect the user's browser to the Djoser/social-auth URL
        return redirect(djoser_social_auth_url)

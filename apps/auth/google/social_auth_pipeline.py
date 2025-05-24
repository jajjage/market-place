from apps.users.models.user_profile import UserProfile
from apps.users.models.user_address import UserAddress
import logging

logger = logging.getLogger(__name__)


def store_user_details(
    backend, strategy, details, response, user=None, *args, **kwargs
):
    """Store user details from OAuth response"""
    if not user:
        return None

    changed = False

    if backend.name == "google-oauth2":
        # Always update first and last name if they exist in the response
        if "first_name" in details:
            user.first_name = details["first_name"]
            changed = True
            logger.info(f"Updated first name for user: {user.email}")

        if "last_name" in details:
            user.last_name = details["last_name"]
            changed = True
            logger.info(f"Updated last name for user: {user.email}")

        # Store profile picture URL temporarily
        if response.get("picture"):
            user.temp_profile_picture_url = response["picture"]
            changed = True
            logger.info(f"Updated profile picture URL for user: {user.email}")

        if changed:
            user.save()
            logger.info(f"Saved user details for: {user.email}")

    return {"user": user}


def store_oauth_data(strategy, details, backend, user=None, *args, **kwargs):
    """Store OAuth data like profile picture URL for later use"""
    if not user:
        return None

    if backend.name == "google-oauth2":
        response = kwargs.get("response", {})
        if "picture" in response:
            # Store the profile picture URL temporarily
            user.temp_profile_picture_url = response["picture"]
            user.save(update_fields=["temp_profile_picture_url"])

    return {"user": user}


def create_user_profile(backend, user, is_new=False, *args, **kwargs):
    """Create appropriate profile based on user type, and save avatar_url instead of file."""

    profile_exists = UserProfile.objects.filter(user=user).exists()
    address_exists = UserAddress.objects.filter(user=user).exists()

    if user and not (profile_exists or address_exists):
        try:
            profile, created = UserProfile.objects.get_or_create(user=user)
            UserAddress.objects.create(user=user)
            logger.info(f"Created seller profile for user: {user.email}")

            # --- NEW: Save Google picture URL instead of downloading ---
            if backend.name == "google-oauth2":
                picture_url = kwargs.get("response", {}).get("picture")
                if picture_url:
                    profile.avatar_url = picture_url
                    profile.save(update_fields=["avatar_url"])
                    logger.info(f"Saved avatar_url for user: {user.email}")
            # -----------------------------------------------------------

        except Exception as e:
            logger.error(f"Failed to create profile: {e}")

    return {
        "profile_exists": profile_exists or address_exists,
    }

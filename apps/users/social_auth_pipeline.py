from apps.users.models.user_profile import UserProfile
from apps.users.models.user_address import UserAddress
import logging

logger = logging.getLogger(__name__)


def set_user_type(strategy, details, backend, user=None, *args, **kwargs):
    """Set the user type based on request parameters or return None for normal flow"""
    if not user:
        return None

    # Get the user type from request parameters
    request = strategy.request
    if request:
        user_type = request.GET.get("user_type")
        logger.info(f"Found user_type: {user_type}")

        if user_type:
            user.user_type = user_type
            user.save()
        else:
            logger.warning("No user_type parameter found in request")

    return {"user": user}


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


def activate_social_user(backend, user, response, *args, **kwargs):
    """Activate the user and set their verification status."""

    # Always check and set these fields, not just for new users
    was_updated = False

    if not user.is_active:
        user.is_active = True
        was_updated = True
        logger.info(f"Activated user: {user.first_name or user.email}")

    if hasattr(user, "verification_status") and user.verification_status != "VERIFIED":
        user.verification_status = "VERIFIED"
        was_updated = True
        logger.info(
            f"Set verification status to VERIFIED for user: {user.first_name or user.email}"
        )

    if hasattr(user, "user_type") and user.user_type == "ADMIN" and not user.is_staff:
        user.is_staff = True
        was_updated = True
        logger.info(
            f"Set is_staff=True for ADMIN user: {user.first_name or user.email}"
        )

    if was_updated:
        user.save()
        logger.info(f"Saved updated user: {user.first_name or user.email}")

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
    if not user.user_type:
        return None

    profile_exists = UserProfile.objects.filter(user=user).exists()
    address_exists = UserAddress.objects.filter(user=user).exists()

    if user.user_type == "SELLER" and not profile_exists:
        try:
            profile, created = UserProfile.objects.get_or_create(user=user)
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
            logger.error(f"Failed to create seller profile: {e}")

    elif user.user_type == "BUYER" and not address_exists:
        try:
            UserAddress.objects.create(user=user)
            logger.info(f"Created buyer address for user: {user.email}")
        except Exception as e:
            logger.error(f"Failed to create buyer address: {e}")

    return {
        "profile_exists": profile_exists or address_exists,
        "user_type": user.user_type,
    }

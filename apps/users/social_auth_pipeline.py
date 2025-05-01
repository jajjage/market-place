from apps.users.models.user_profile import UserProfile
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

    # Store first and last name if available
    if backend.name == "google-oauth2":
        if details.get("first_name") and not user.first_name:
            user.first_name = details["first_name"]
            changed = True

        if details.get("last_name") and not user.last_name:
            user.last_name = details["last_name"]
            changed = True

        # Store profile picture URL temporarily
        if response.get("picture"):
            user.temp_profile_picture_url = response["picture"]
            changed = True

        if changed:
            user.save()

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
    # Check if a profile already exists
    profile_exists = UserProfile.objects.filter(user=user).exists()

    # Only proceed if a profile doesn't exist and the user is either new or a SELLER
    if not profile_exists and (is_new or user.user_type == "SELLER"):
        try:
            # Use get_or_create to avoid race conditions
            profile, created = UserProfile.objects.get_or_create(user=user)

            # Process profile picture from social auth if available
            if backend.name == "google-oauth2" and "picture" in kwargs.get(
                "response", {}
            ):
                try:
                    import requests
                    from django.core.files.base import ContentFile
                    from urllib3.util.retry import Retry
                    from requests.adapters import HTTPAdapter

                    # Configure session with retries
                    session = requests.Session()
                    retries = Retry(total=3, backoff_factor=0.1)
                    session.mount("http://", HTTPAdapter(max_retries=retries))
                    session.mount("https://", HTTPAdapter(max_retries=retries))

                    picture_url = kwargs["response"]["picture"]
                    img_response = session.get(picture_url, stream=True)

                    if img_response.status_code == 200:
                        # Don't try to decode the binary content
                        file_name = f"profile_{user.id}.jpg"
                        profile.profile_picture.save(
                            file_name, ContentFile(img_response.raw.read()), save=True
                        )
                except Exception as e:
                    logger.error(f"Failed to save OAuth profile picture: {e}")
        except Exception as e:
            logger.error(f"Failed to create user profile: {e}")

    return {"profile_exists": profile_exists}

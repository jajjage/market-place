def set_user_type(strategy, details, backend, user=None, *args, **kwargs):
    """Set the user_type based on the request parameters."""

    # Extract user_type from the request parameters
    request = strategy.request

    # Try to get user_type from different possible sources
    user_type = None

    # Check GET parameters
    user_type = request.GET.get("user_type")

    # If not found in GET, check POST data
    if not user_type and hasattr(request, "POST"):
        user_type = request.POST.get("user_type")

    # If not found in POST, try to parse it from the URL
    if not user_type and request.path:
        # Log the URL to debug
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Auth URL: {request.path}")
        logger.info(
            f"Full request data: GET={request.GET}, POST={getattr(request, 'POST', {})}"
        )

    # Debug logging
    logger.info(f"Found user_type: {user_type}")

    if user_type:
        # For new users, add it to the details dict
        if not user:
            details["user_type"] = user_type
            logger.info(f"Setting user_type for new user to: {user_type}")
        # For existing users, update the field if needed
        elif user and hasattr(user, "user_type"):
            # Log before update
            logger.info(f"Existing user current user_type: {user.user_type}")

            if user.user_type != user_type:
                user.user_type = user_type
                user.save()
                logger.info(f"Updated user_type to: {user_type}")
            else:
                logger.info(f"User already has correct user_type: {user_type}")
    else:
        logger.warning("No user_type parameter found in request")

    return {"details": details}


def activate_social_user(backend, user, response, *args, **kwargs):
    """Activate the user and set their verification status."""

    import logging

    logger = logging.getLogger(__name__)

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


def create_user_profile(backend, user, response, *args, **kwargs):
    """If the user doesn't have a profile, create a UserProfile instance."""

    import logging

    logger = logging.getLogger(__name__)

    # Import your Profile model
    from apps.users.models import UserProfile

    # Check if profile already exists
    try:
        profile = UserProfile.objects.get(user=user)
        logger.info(
            f"User profile already exists for user: {user.first_name or user.email}"
        )
    except UserProfile.DoesNotExist:
        # Create UserProfile
        profile = UserProfile(
            user=user,
            # Set default profile values here
            # You can also extract data from the OAuth response if needed
        )
        profile.save()
        logger.info(f"Created new profile for user: {user.first_name or user.email}")

    return {"profile": profile}

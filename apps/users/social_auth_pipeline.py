def set_user_type(strategy, details, backend, user=None, *args, **kwargs):
    # Extract user_type from the request parameters
    request = strategy.request
    user_type = request.GET.get("user_type")

    if user_type:
        # For new users, add it to the details dict
        if not user:
            details["user_type"] = user_type
        # For existing users, update the field if needed
        elif user and hasattr(user, "user_type") and user.user_type != user_type:
            user.user_type = user_type
            user.save()

    return {"details": details}


def activate_social_user(backend, user, response, *args, **kwargs):
    if kwargs.get("is_new", False):
        user.is_active = True
        user.verification_status = "VERIFIED"
        if user.user_type == "ADMIN":
            user.is_staff = True
        user.save()
    return {"user": user}


def create_user_profile(backend, user, response, *args, **kwargs):
    # Only run this for newly created users
    if kwargs.get("is_new", False):
        # Import your Profile model
        from apps.users.models import UserProfile

        # Check if profile already exists (unlikely but good practice)
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            # Create UserProfile
            profile = UserProfile(
                user=user,
                # Set default profile values here
                # You can also extract data from the OAuth response if needed
                # For example, for Google:
                # profile_picture=response.get('picture', ''),
                # You can also use data from user like:
                # display_name=user.get_full_name(),
            )
            profile.save()

    return {"profile": getattr(user, "profile", None)}

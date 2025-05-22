class CreateUserProfile:
    """Create appropriate profile based on user type, but only when user_type is set"""

    # Skip if user_type is not set yet (initial OAuth creation)
    if not instance.user_type:
        return

    # First, check if any profile already exists
    if (
        UserProfile.objects.filter(user=instance).exists()
        or UserAddress.objects.filter(user=instance).exists()
    ):
        return

    # Create appropriate profile based on user type
    with transaction.atomic():
        UserAddress.objects.get_or_create(user=instance)

        profile, _ = UserProfile.objects.get_or_create(user=instance)

        # Instead of downloading, just store the URL in avatar_url
        temp_url = getattr(instance, "temp_profile_picture_url", None)
        if temp_url:
            profile.avatar_url = temp_url
            profile.save(update_fields=["avatar_url"])

            # Clear the temp field on the user
            instance.temp_profile_picture_url = None
            instance.save(update_fields=["temp_profile_picture_url"])

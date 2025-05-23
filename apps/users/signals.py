from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction


from apps.users.models.base import CustomUser
from apps.users.models.user_address import UserAddress
from apps.users.models.user_profile import UserProfile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create appropriate profile based on user type, but only when user_type is set"""

    # First, check if any profile already exists
    if (
        UserProfile.objects.filter(user=instance).exists()
        and UserAddress.objects.filter(user=instance).exists()
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

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction


from apps.users.models.base import CustomUser
from apps.users.models.user_address import UserAddress
from apps.users.models.user_profile import UserProfile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
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
        if instance.user_type == "BUYER":
            UserAddress.objects.get_or_create(user=instance)

        elif instance.user_type == "SELLER":
            profile, _ = UserProfile.objects.get_or_create(user=instance)

            # Instead of downloading, just store the URL in avatar_url
            temp_url = getattr(instance, "temp_profile_picture_url", None)
            if temp_url:
                profile.avatar_url = temp_url
                profile.save(update_fields=["avatar_url"])

                # Clear the temp field on the user
                instance.temp_profile_picture_url = None
                instance.save(update_fields=["temp_profile_picture_url"])


@receiver(pre_save, sender=CustomUser)
def handle_user_type_change(sender, instance, **kwargs):
    """Detect user_type changes and create profile when needed"""
    if instance.pk:  # Only for existing users (not new ones)
        try:
            old_instance = CustomUser.objects.get(pk=instance.pk)
            # Check if user_type is being changed to SELLER
            if (
                old_instance.user_type != "SELLER"
                and instance.user_type == "SELLER"
                or old_instance.user_type != "BUYER"
                and instance.user_type == "BUYER"
            ):
                # We'll create profile after save to ensure user is saved first
                instance._create_seller_or_buyer_profile = True
        except CustomUser.DoesNotExist:
            pass


@receiver(post_save, sender=CustomUser)
def create_profile_after_type_change(sender, instance, **kwargs):
    """Create profile after user_type is changed to SELLER"""
    if (
        hasattr(instance, "_create_seller_or_buyer_profile")
        and instance._create_seller_or_buyer_profile
    ):
        # Remove the flag first to prevent recursion
        instance._create_seller_or_buyer_profile = False
        # Call the main profile creation function
        create_user_profile(sender, instance, created=False)

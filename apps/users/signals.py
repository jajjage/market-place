from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
import requests
from django.core.files.base import ContentFile

from apps.users.models.base import CustomUser
from apps.users.models.user_profile import UserProfile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Only create profile for SELLER and only when the profile doesn't already exist"""
    # First, check if a profile already exists
    if UserProfile.objects.filter(user=instance).exists():
        return

    # Only create profile for SELLER and only when the profile doesn't already exist
    if instance.user_type == "SELLER":
        with transaction.atomic():
            # Use get_or_create to avoid race conditions
            profile, created = UserProfile.objects.get_or_create(user=instance)

            # If we have a saved profile picture URL from OAuth, use it
            if (
                hasattr(instance, "temp_profile_picture_url")
                and instance.temp_profile_picture_url
            ):
                try:
                    # Get the image
                    img_response = requests.get(instance.temp_profile_picture_url)

                    if img_response.status_code == 200:
                        # Save it to the profile
                        file_name = f"profile_{instance.id}.jpg"
                        profile.profile_picture.save(
                            file_name, ContentFile(img_response.content), save=True
                        )

                        # Clear the temporary URL
                        instance.temp_profile_picture_url = None
                        instance.save(update_fields=["temp_profile_picture_url"])
                except Exception as e:
                    # Log the error but don't break the flow
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to save OAuth profile picture: {e}")


@receiver(pre_save, sender=CustomUser)
def handle_user_type_change(sender, instance, **kwargs):
    """Detect user_type changes and create profile when needed"""
    if instance.pk:  # Only for existing users (not new ones)
        try:
            old_instance = CustomUser.objects.get(pk=instance.pk)
            # Check if user_type is being changed to SELLER
            if old_instance.user_type != "SELLER" and instance.user_type == "SELLER":
                # We'll create profile after save to ensure user is saved first
                instance._create_seller_profile = True
        except CustomUser.DoesNotExist:
            pass


@receiver(post_save, sender=CustomUser)
def create_profile_after_type_change(sender, instance, **kwargs):
    """Create profile after user_type is changed to SELLER"""
    if hasattr(instance, "_create_seller_profile") and instance._create_seller_profile:
        # Remove the flag first to prevent recursion
        instance._create_seller_profile = False
        # Call the main profile creation function
        create_user_profile(sender, instance, created=False)

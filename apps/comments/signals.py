# In signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Avg, Count

from apps.comments.models import UserRating
from apps.users.models.user_profile import UserProfile


@receiver(post_save, sender=UserRating)
def update_user_rating_stats(sender, instance, created, **kwargs):
    if created:
        # Update the rated user's statistics
        stats = UserRating.objects.filter(to_user=instance.to_user).aggregate(
            avg_rating=Avg("rating"), total_ratings=Count("rating")
        )

        # Update user profile
        profile, created = UserProfile.objects.get_or_create(user=instance.to_user)
        profile.average_rating = stats["avg_rating"]
        profile.total_ratings = stats["total_ratings"]
        profile.save()

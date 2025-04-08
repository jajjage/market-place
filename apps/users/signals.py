# In your signals.py file
from django.dispatch import Signal, receiver

from apps.users.models import UserProfile

user_activated_signal = Signal()  # providing_args=['user']


@receiver(user_activated_signal)
def create_profile_on_activation(sender, user, **kwargs):
    """Create a UserProfile instance when a user is activated."""
    UserProfile.objects.get_or_create(user=user)

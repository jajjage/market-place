from django.db import models
from apps.core.models import BaseModel
from django.conf import settings


class UserProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    # Identity and presentation
    display_name = models.CharField(max_length=100, blank=True)
    avatar_url = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True)

    # Rating and feedback
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, default=0.0
    )
    total_ratings = models.PositiveIntegerField(default=0)

    # Verification
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    identity_verified = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # Overall verification status

    # Contact information
    phone_number = models.CharField(max_length=20, blank=True)
    response_rate = models.PositiveIntegerField(default=0)  # Percentage
    response_time = models.CharField(max_length=50, default="< 24 hours")

    # Location
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)  # Combined location string

    # Account statistics
    member_since = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    positive_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.0
    )

    # Settings and preferences
    notification_email = models.BooleanField(default=True)
    notification_sms = models.BooleanField(default=False)

    class Meta:
        db_table = "user_profiles"
        verbose_name_plural = "User Profiles"
        ordering = ["-member_since"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["email_verified"]),
            models.Index(fields=["phone_verified"]),
        ]

    def __str__(self):
        return self.user.first_name

    # -----------------------------------------------------------------------------
    # I may remove this in the future
    # -----------------------------------------------------------------------------

    def get_full_name(self):
        """Return the full name of the user."""
        return f"{self.user.first_name} {self.user.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.avatar_url:
            self.avatar_url = None  # Ensure it's explicitly None
        super().save(*args, **kwargs)

    @property
    def verified_status(self):
        if self.identity_verified:
            return "ID Verified"
        elif self.email_verified and self.phone_verified:
            return "Contact Verified"
        elif self.email_verified:
            return "Email Verified"
        return "Unverified"

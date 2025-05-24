from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel

from apps.users.managers import CustomUserManager


class VerificationStatus(models.TextChoices):
    """User verification status choices"""

    UNVERIFIED = "UNVERIFIED", "Unverified"
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"


class CustomUser(AbstractUser, BaseModel):
    """
    CustomUser is a custom user model that extends Django's AbstractUser.
    It uses email as the unique identifier instead of the username.
    """

    # The username field is set to None to disable it.
    username = None

    # The email field is set to be unique because it is the unique identifier.
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    temp_profile_picture_url = models.URLField(
        null=True, blank=True
    )  # Temporary storage for OAuth profile pic URL

    # Additional fields for Django's authentication system
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Specifies the field to be used as the unique identifier for the user.
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
    ]

    objects = CustomUserManager()

    class Meta:
        db_table = "core_user"
        indexes = [
            models.Index(fields=["email", "is_active"]),
            models.Index(fields=["first_name", "last_name"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email__isnull=False), name="staff_email_not_null"
            )
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        return self.first_name or self.email.split("@")[0]

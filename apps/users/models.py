import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, SoftDeleteBaseModel

from .managers import CustomUserManager


class UserType(models.TextChoices):
    """User type choices"""

    BUYER = "BUYER", "Buyer"
    SELLER = "SELLER", "Seller"
    ADMIN = "ADMIN", "Admin"


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # The username field is set to None to disable it.
    username = None

    # The email field is set to be unique because it is the unique identifier.
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    user_type = models.CharField(max_length=10, choices=UserType.choices)
    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.VERIFIED,
    )

    # Additional fields for Django's authentication system
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Specifies the field to be used as the unique identifier for the user.
    USERNAME_FIELD = "email"

    # A list of fields that will be prompted for when creating a user
    # via the createsuperuser command. If empty, the USERNAME_FIELD is
    # the only required.
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "user_type",
    ]

    # The CustomUserManager allows the creation of a user where email
    # is the unique identifier.
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


class UserProfile(SoftDeleteBaseModel):
    """Extended profile information for users."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="profile"
    )
    bio = models.TextField(blank=True)
    address = models.JSONField(default=dict, blank=True)
    profile_picture = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    id_verification_documents = models.JSONField(default=dict, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    total_reviews = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    social_links = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Profile for {self.user.email}"

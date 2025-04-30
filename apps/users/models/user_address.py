from django.db import models
from apps.core.models import BaseModel
from django.conf import settings


class UserAddress(BaseModel):
    """UserAddress is a model representing a user's address."""

    ADDRESS_TYPES = [
        ("shipping", "Shipping Address"),
        ("billing", "Billing Address"),
        ("both", "Shipping & Billing"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    address_type = models.CharField(
        max_length=10, choices=ADDRESS_TYPES, default="both"
    )
    is_default = models.BooleanField(default=False)

    name = models.CharField(max_length=100)  # Name for this address
    street_address = models.CharField(max_length=255)
    apartment = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)

    class Meta:
        db_table = "user_addresses"
        verbose_name_plural = "User Addresses"
        ordering = ["-created_at"]
        unique_together = ("user", "address_type")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["address_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_address_type_display()})"

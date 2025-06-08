from django.db import models
from apps.core.models import BaseModel
from django.conf import settings
from apps.products.product_breadcrumb.models import Breadcrumb
from django.contrib.contenttypes.fields import GenericRelation


# Store for sellers - optional, for users who sell regularly
class UserStore(BaseModel):
    """
    UserStore is a model representing a seller's store.
    It contains information about the store, including its name, logo, and policies.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="store"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to="store_logos/", null=True, blank=True)
    banner = models.ImageField(upload_to="store_banners/", null=True, blank=True)
    description = models.TextField(blank=True)
    breadcrumbs = GenericRelation(Breadcrumb)
    is_active = models.BooleanField(default=True)

    # Store policies
    return_policy = models.TextField(blank=True)
    shipping_policy = models.TextField(blank=True)

    # Social media
    website = models.URLField(blank=True)

    class Meta:
        db_table = "user_stores"
        verbose_name_plural = "User Stores"
        ordering = ["-created_at"]
        unique_together = ("user", "slug")
        constraints = [
            models.UniqueConstraint(fields=["user", "slug"], name="unique_user_store")
        ]
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

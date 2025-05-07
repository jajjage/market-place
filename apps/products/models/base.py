from django.db import models
from django.conf import settings
from django.urls import reverse
from django.db.models import JSONField

from apps.core.models import BaseModel


class ProductsStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    INACTIVE = "INACTIVE", "Inactive"


class Product(BaseModel):
    # Core fields all products have
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")
    category = models.ForeignKey("Category", on_delete=models.PROTECT)
    condition = models.ForeignKey("ProductCondition", on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    total_inventory = models.IntegerField(default=0)
    available_inventory = models.IntegerField(default=0)
    in_escrow_inventory = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=12, choices=ProductsStatus.choices, default=ProductsStatus.DRAFT
    )

    # Dynamic specifications field using JSONField
    specifications = JSONField(default=dict, blank=True)

    slug = models.SlugField(max_length=255, blank=True, db_index=True)
    short_code = models.CharField(
        max_length=200, unique=True, blank=True, null=True, db_index=True
    )

    class Meta:
        db_table = "products"
        ordering = ["-created_at"]
        verbose_name_plural = "Products"
        unique_together = ("slug", "short_code")
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["short_code"]),
        ]

    def discount_percentage(self):
        if self.original_price and self.original_price > self.price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0

    def get_absolute_url(self):
        return reverse("product-detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title


class InventoryTransaction(BaseModel):
    TRANSACTION_TYPES = (
        ("ADD", "Add to Total"),
        ("ACTIVATE", "Make Available"),
        ("ESCROW", "Place in Escrow"),
        ("COMPLETE", "Complete Transaction"),
        ("CANCEL", "Cancel Escrow"),
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="inventory_transactions"
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.product.title}"

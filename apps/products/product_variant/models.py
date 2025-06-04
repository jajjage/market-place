from django.db import models
from apps.core.models import BaseModel


class ProductVariantType(BaseModel):
    """Defines the type of variant for a product, such as size, color, etc."""

    name = models.CharField(max_length=50, unique=True, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        db_table = "product_variant_type"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["is_active", "sort_order"]),
        ]

    def __str__(self):
        return self.name


class ProductVariantOption(BaseModel):
    """Individual options for variant types"""

    variant_type = models.ForeignKey(
        ProductVariantType,
        on_delete=models.CASCADE,
        related_name="options",
        db_index=True,
    )
    value = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "product_variant_option"
        unique_together = [["variant_type", "value"]]
        ordering = ["sort_order", "value"]
        indexes = [
            models.Index(fields=["variant_type", "is_active", "sort_order"]),
        ]

    def __str__(self):
        return f"{self.variant_type.name}: {self.value}"


class ProductVariant(BaseModel):
    """Specific variant combination for a product"""

    product = models.ForeignKey(
        "product_base.Product",
        on_delete=models.CASCADE,
        related_name="variants",
        db_index=True,
    )
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    options = models.ManyToManyField(ProductVariantOption, related_name="variants")

    # Pricing and inventory
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "product_variant"
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self):
        return f"{self.product.title} - {self.sku}"

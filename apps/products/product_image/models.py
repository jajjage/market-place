import logging
from django.db import models
from django.core.files.storage import default_storage
from apps.core.models import BaseModel

logger = logging.getLogger("images_performance")


class ProductImageVariant(BaseModel):
    """Predefined image variants (e.g., thumbnail, medium, large, zoom)"""

    name = models.CharField(max_length=50, unique=True)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    quality = models.PositiveIntegerField(default=85)
    is_active = models.BooleanField(default=True)
    created_by_admin = models.BooleanField(default=True)

    class Meta:
        db_table = "product_image_variants"
        ordering = ["name"]


class ProductImage(BaseModel):
    product = models.ForeignKey(
        "product_base.Product", on_delete=models.CASCADE, related_name="images"
    )
    image_url = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    variant = models.ForeignKey(
        ProductImageVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="images",
    )
    created_by_user = models.BooleanField(default=False)  # Track if user-generated

    # File storage fields
    file_path = models.CharField(max_length=500, blank=True)  # Relative path to file
    file_size = models.PositiveIntegerField(default=0)  # File size in bytes
    width = models.PositiveIntegerField(default=0)  # Image width
    height = models.PositiveIntegerField(default=0)  # Image height

    class Meta:
        db_table = "product_product_images"
        ordering = ["display_order"]
        verbose_name_plural = "Product Images"
        indexes = [
            models.Index(fields=["product", "is_primary"]),
            models.Index(fields=["product", "variant", "display_order"]),
            models.Index(fields=["is_active", "product"]),
        ]

    def __str__(self):
        return f"Image for {self.product.title}"

    def delete(self, *args, **kwargs):
        # Delete file when model is deleted
        if self.file_path:
            try:
                default_storage.delete(self.file_path)
            except Exception as e:
                logger.warning(f"Could not delete file {self.file_path}: {str(e)}")
        super().delete(*args, **kwargs)

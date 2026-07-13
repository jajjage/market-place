from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel
from django.conf import settings


class ProductCondition(BaseModel):
    """
    Enhanced Product Condition model with additional features.
    """

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=60, unique=True, db_index=True)

    # Quality score for condition (1-10, where 10 is perfect)
    quality_score = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Quality score from 1 (poor) to 10 (perfect)",
    )

    # Price adjustment factor (e.g., 0.8 for 80% of original price)
    price_factor = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=1.000,
        validators=[MinValueValidator(0.1), MaxValueValidator(2.0)],
        help_text="Price adjustment factor (0.1 to 2.0)",
    )

    # Display order for frontend
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    # Color coding for UI
    color_code = models.CharField(
        max_length=7, default="#28a745", help_text="Hex color code for UI display"
    )

    # Icon for UI
    icon_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name for UI (e.g., 'star', 'check-circle')",
    )

    is_active = models.BooleanField(default=True, db_index=True)

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_conditions",
    )

    class Meta:
        db_table = "product_product_conditions"
        verbose_name = "Product Condition"
        verbose_name_plural = "Product Conditions"
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["is_active", "display_order"]),
            models.Index(fields=["quality_score"]),
        ]

    def __str__(self):
        return f"{self.name} (Score: {self.quality_score})"

from django.db import models
from apps.core.models import BaseModel
from apps.products.product_base.models import Product


class ProductDetailTemplate(BaseModel):
    """Admin-defined templates for consistent product details"""

    class DetailType(models.TextChoices):
        SPECIFICATION = "specification", "Specification"
        FEATURE = "feature", "Feature"
        DESCRIPTION = "description", "Description"
        WARNING = "warning", "Warning"
        CARE_INSTRUCTION = "care_instruction", "Care Instruction"
        DIMENSION = "dimension", "Dimension"
        MATERIAL = "material", "Material"
        COMPATIBILITY = "compatibility", "Compatibility"
        OTHER = "other", "Other"

    detail_type = models.CharField(
        max_length=20, choices=DetailType.choices, default=DetailType.OTHER
    )
    label = models.CharField(max_length=100)
    unit = models.CharField(max_length=20, blank=True)
    is_required = models.BooleanField(default=False)
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Category-specific template",
    )
    placeholder_text = models.TextField(blank=True)
    validation_regex = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "product_detail_templates"
        ordering = ["display_order", "label"]
        unique_together = [["label", "category", "detail_type"]]
        indexes = [
            models.Index(fields=["detail_type"]),
            models.Index(fields=["category", "detail_type"]),
        ]

    def __str__(self):
        return f"{self.label} ({self.get_detail_type_display()})"


class ProductDetail(BaseModel):
    """Enhanced ProductDetail model with better indexing"""

    class DetailType(models.TextChoices):
        SPECIFICATION = "specification", "Specification"
        FEATURE = "feature", "Feature"
        DESCRIPTION = "description", "Description"
        WARNING = "warning", "Warning"
        CARE_INSTRUCTION = "care_instruction", "Care Instruction"
        DIMENSION = "dimension", "Dimension"
        MATERIAL = "material", "Material"
        COMPATIBILITY = "compatibility", "Compatibility"
        OTHER = "other", "Other"

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_details"
    )
    template = models.ForeignKey(
        ProductDetailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_details",
    )
    detail_type = models.CharField(
        max_length=20, choices=DetailType.choices, default=DetailType.OTHER
    )
    label = models.CharField(max_length=100)
    value = models.TextField()
    unit = models.CharField(max_length=20, blank=True)
    is_highlighted = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product_product_details"
        ordering = ["display_order", "label"]
        verbose_name_plural = "Product Details"
        indexes = [
            models.Index(fields=["product", "detail_type"]),
            models.Index(fields=["product", "is_highlighted"]),
            models.Index(fields=["product", "display_order"]),
            models.Index(fields=["detail_type", "is_highlighted"]),
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["template"]),
        ]
        unique_together = [["product", "label", "detail_type"]]

    def __str__(self):
        return f"{self.product.title} - {self.label}: {self.value}"

    @property
    def formatted_value(self):
        """Returns formatted value with unit if available"""
        if self.unit:
            return f"{self.value} {self.unit}"
        return self.value

    def save(self, *args, **kwargs):
        # Auto-populate from template if available
        if self.template and not self.unit:
            self.unit = self.template.unit
        if self.template and not self.detail_type:
            self.detail_type = self.template.detail_type
        super().save(*args, **kwargs)

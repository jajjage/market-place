from django.db import models
from django.core.exceptions import ValidationError
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

    # NEW: Add fields to support better template management
    description = models.TextField(
        blank=True, help_text="Template description for admins"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this template is available for use"
    )
    applies_to_subcategories = models.BooleanField(
        default=True, help_text="Whether this template applies to subcategories as well"
    )

    class Meta:
        db_table = "product_detail_templates"
        ordering = ["display_order", "label"]
        indexes = [
            models.Index(fields=["detail_type"]),
            models.Index(fields=["category", "detail_type"]),
            models.Index(fields=["is_active"]),  # NEW
            models.Index(fields=["category", "is_active"]),  # NEW
        ]

    def __str__(self):
        category_name = self.category.name if self.category else "Global"
        return f"{self.label} ({self.get_detail_type_display()}) - {category_name}"

    def clean(self):
        """Validate template data"""
        super().clean()
        if self.validation_regex:
            try:
                import re

                re.compile(self.validation_regex)
            except re.error:
                raise ValidationError({"validation_regex": "Invalid regex pattern"})


class ProductDetail(BaseModel):
    """Enhanced ProductDetail model with better template integration"""

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

    # NEW: Add fields for better template integration
    created_from_template = models.BooleanField(
        default=False, help_text="Whether this detail was created from a template"
    )
    template_version = models.PositiveIntegerField(
        default=1, help_text="Version of template when this detail was created"
    )

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
            models.Index(fields=["created_from_template"]),  # NEW
        ]

    def __str__(self):
        return f"{self.product.title} - {self.label}: {self.value}"

    @property
    def formatted_value(self) -> str:
        """Returns formatted value with unit if available"""
        if self.unit:
            return f"{self.value} {self.unit}"
        return self.value

    def clean(self):
        """Validate detail against template if available"""
        super().clean()
        if self.template and self.template.validation_regex and self.value:
            import re

            pattern = self.template.validation_regex
            if not re.match(pattern, str(self.value)):
                raise ValidationError(
                    {"value": f"Value does not match required pattern: {pattern}"}
                )

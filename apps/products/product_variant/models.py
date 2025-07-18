from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel


class ProductVariantType(BaseModel):
    """Defines the type of variant for a product, such as size, color, etc."""

    name = models.CharField(max_length=50, unique=True, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)

    # New fields for enhanced functionality
    is_required = models.BooleanField(
        default=True, help_text="Whether this variant type is required for all products"
    )
    display_type = models.CharField(
        max_length=20,
        choices=[
            ("dropdown", "Dropdown"),
            ("radio", "Radio Buttons"),
            ("color_swatch", "Color Swatch"),
            ("image_swatch", "Image Swatch"),
            ("text", "Text Input"),
        ],
        default="dropdown",
        help_text="How this variant should be displayed to customers",
    )
    affects_price = models.BooleanField(
        default=False, help_text="Whether this variant type can affect pricing"
    )
    affects_inventory = models.BooleanField(
        default=True, help_text="Whether this variant type affects inventory tracking"
    )

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

    # Enhanced fields
    display_value = models.CharField(
        max_length=100, blank=True, help_text="Display name if different from value"
    )
    color_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text="Hex color code for color swatches",
    )
    image = models.ImageField(upload_to="variant_options/", blank=True, null=True)
    price_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Price adjustment for this option (can be negative)",
    )

    class Meta:
        db_table = "product_variant_option"
        unique_together = [["variant_type", "value"]]
        ordering = ["sort_order", "value"]
        indexes = [
            models.Index(fields=["variant_type", "is_active", "sort_order"]),
        ]

    def clean(self):
        # Validation for color swatches
        if self.variant_type.display_type == "color_swatch" and not self.color_code:
            raise ValidationError(
                "Color code is required for color swatch display type"
            )

    def __str__(self):
        return f"{self.variant_type.name}: {self.display_value or self.value}"


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
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost to acquire/produce this variant",
    )
    total_inventory = models.IntegerField(default=0)
    in_escrow_inventory = models.PositiveIntegerField(
        default=0, help_text="Quantity reserved for pending orders"
    )
    available_inventory = models.IntegerField(default=0)  # Inspected & ready
    pending_inspection = models.IntegerField(default=0)  # Items awaiting inspection
    rejected_inventory = models.IntegerField(default=0)  # Failed inspection
    low_stock_threshold = models.PositiveIntegerField(
        default=5, help_text="Alert when stock falls below this level"
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Enhanced fields for e-commerce/escrow
    weight = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True, help_text="Weight in kg"
    )
    dimensions_length = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text="Length in cm"
    )
    dimensions_width = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text="Width in cm"
    )
    dimensions_height = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text="Height in cm"
    )

    # Track availability and status
    is_digital = models.BooleanField(
        default=False, help_text="Whether this is a digital product"
    )
    is_backorderable = models.BooleanField(
        default=False, help_text="Can be ordered when out of stock"
    )
    expected_restock_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "product_variant"
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["total_inventory"]),
            models.Index(fields=["is_active", "total_inventory"]),
        ]

    def __str__(self):
        options_str = " - ".join([str(option) for option in self.options.all()[:3]])
        return f"{self.product.title} - {options_str} ({self.sku})"

    def clean(self):
        """Validate variant data"""
        if self.in_escrow_inventory > self.total_inventory:
            raise ValidationError("Reserved quantity cannot exceed stock quantity")

        if self.is_digital and self.product.requires_shipping:
            raise ValidationError("Digital products should not require shipping")

    @property
    def available_quantity(self):
        """Calculate available quantity (stock - reserved)"""
        return max(0, self.total_inventory - self.in_escrow_inventory)

    @property
    def is_in_stock(self):
        """Check if variant is in stock"""
        return self.available_quantity > 0 or self.is_backorderable

    @property
    def is_low_stock(self):
        """Check if variant is low on stock"""
        return self.available_quantity <= self.low_stock_threshold

    @property
    def final_price(self):
        """Calculate final price including option adjustments"""
        if self.price is None:
            return self.product.price if hasattr(self, "product") else None

        base_price = self.price
        option_adjustments = sum(
            option.price_adjustment
            for option in self.options.all()
            if option.variant_type.affects_price
        )
        return base_price + option_adjustments

    def reserve_stock(self, quantity):
        """Reserve stock for pending orders"""
        if self.available_quantity >= quantity:
            self.in_escrow_inventory += quantity
            self.save(update_fields=["in_escrow_inventory"])
            return True
        return False

    def release_stock(self, quantity):
        """Release reserved stock"""
        self.in_escrow_inventory = max(0, self.in_escrow_inventory - quantity)
        self.save(update_fields=["in_escrow_inventory"])

    def reduce_stock(self, quantity):
        """Reduce actual stock quantity"""
        if self.total_inventory >= quantity:
            self.total_inventory -= quantity
            self.in_escrow_inventory = max(0, self.in_escrow_inventory - quantity)
            self.save(update_fields=["total_inventory", "in_escrow_inventory"])
            return True
        return False


class ProductVariantImage(BaseModel):
    """Images specific to product variants"""

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="variant_images/")
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "product_variant_image"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["variant", "sort_order"]),
        ]

    def __str__(self):
        return f"Image for {self.variant.sku}"

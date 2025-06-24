from django.conf import settings
from django.db import models, IntegrityError, transaction


from apps.core.models import BaseModel
from apps.products.product_base.utils.social_sharing import (
    create_unique_short_code,
    generate_seo_friendly_slug,
)
from apps.products.product_brand.models import Brand


class Product(BaseModel):
    class ProductsStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SOLD = "sold", "Sold"

    # Basic product information
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    short_code = models.CharField(
        max_length=200, unique=True, blank=True, null=True, db_index=True
    )

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")
    escrow_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    # Category and condition
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    condition = models.ForeignKey(
        "product_condition.ProductCondition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        help_text="Select the condition of this product",
    )

    # Location
    location = models.CharField(max_length=200, blank=True)

    # Status and inventory
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=12, choices=ProductsStatus.choices, default=ProductsStatus.DRAFT
    )

    # Product details and specifications - Updated to use Brand model
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    authenticity_guaranteed = models.BooleanField(
        default=False
    )  # Indicates if the product's authenticity is guaranteed
    warranty_period = models.CharField(
        max_length=100, blank=True, help_text="Warranty period in months or years"
    )
    requires_shipping = models.BooleanField(default=True)
    # Escrow-specific fields
    escrow_hold_period = models.PositiveIntegerField(
        default=7,
        help_text="Days to hold payment in escrow after delivery confirmation",
    )
    # Negotiation and offers
    is_negotiable = models.BooleanField(default=False)
    requires_inspection = models.BooleanField(default=False)
    minimum_acceptable_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    negotiation_deadline = models.DateTimeField(null=True, blank=True)
    max_negotiation_rounds = models.PositiveIntegerField(default=5)

    class Meta:
        db_table = "product"
        ordering = ["-created_at"]
        verbose_name_plural = "Products"
        unique_together = ("slug", "short_code")
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["short_code"]),
            models.Index(fields=["brand", "is_active"]),  # Added brand index
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # 1) Slug: only for new objects or if slug is blank
        if not self.slug:
            self.slug = generate_seo_friendly_slug(self.title)

        # 2) Short code: only when missing
        if not self.short_code:
            # try a few times in case of race
            for attempt in range(3):
                candidate = create_unique_short_code(self.__class__, length=6)
                # If we have a slug, append it to the short code
                self.short_code = f"{self.slug}-{candidate}"
                try:
                    # Use atomic block to isolate the insert/update
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    break  # success!
                except IntegrityError:
                    if attempt == 2:
                        raise  # out of retries
                    # else – collision, retry
            # We’ve already called super().save() inside the loop
            return

        # default save for objects that already have both fields
        super().save(*args, **kwargs)

    @property
    def brand_name(self):
        """Helper property to get brand name safely"""
        return self.brand.name if self.brand else "No Brand"

    @property
    def average_rating(self):
        ratings = self.product_ratings.all()
        if ratings:
            return sum(r.rating for r in ratings) / len(ratings)
        return 0.0

    @property
    def rating_count(self):
        return self.product_ratings.count()

    @property
    def rating_breakdown(self):
        """Returns rating breakdown similar to the desired format"""
        breakdown = []
        for i in range(1, 6):
            count = self.product_ratings.filter(rating=i).count()
            breakdown.append({"stars": i, "count": count})
        return breakdown

    def discount_percentage(self):
        if self.original_price and self.original_price > self.price:
            return int(((self.original_price - self.price) / self.original_price) * 100)
        return 0

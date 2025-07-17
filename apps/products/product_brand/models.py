from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.core.cache import cache
from django.db.models import Avg
from apps.core.models import BaseModel
from apps.products.product_brand.managers import BrandManager


class Brand(BaseModel):
    """Optimized Brand model with caching and better indexing"""

    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="brands/logos/", blank=True, null=True)
    website = models.URLField(blank=True)
    founded_year = models.PositiveIntegerField(blank=True, null=True, db_index=True)
    country_of_origin = models.CharField(max_length=100, blank=True, db_index=True)

    # SEO and marketing
    meta_description = models.CharField(max_length=160, blank=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)

    # Contact information
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    # Social media
    social_media = models.JSONField(default=dict, blank=True)

    # Status
    is_active = models.BooleanField(default=True, db_index=True)

    # Add materialized fields for frequently accessed data
    cached_product_count = models.PositiveIntegerField(default=0)
    cached_average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00
    )
    stats_updated_at = models.DateTimeField(auto_now=True)

    objects = BrandManager()

    class Meta:
        db_table = "product_brands"
        ordering = ["name"]
        verbose_name_plural = "Brands"
        indexes = [
            # Composite indexes for common query patterns
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["is_active", "is_verified"]),
            models.Index(fields=["country_of_origin", "is_active"]),
            models.Index(fields=["founded_year", "is_active"]),
            # Full-text search support
            models.Index(fields=["name", "country_of_origin"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_stats(self, use_cache=True):
        """Get brand statistics with caching"""
        if not use_cache:
            return self._calculate_stats()

        cache_key = f"{self.cache_key}:stats"
        stats = cache.get(cache_key)

        if stats is None:
            stats = self._calculate_stats()
            cache.set(cache_key, stats, timeout=3600)  # 1 hour cache

        return stats

    def _calculate_stats(self):
        """Calculate brand statistics"""
        products = self.products.filter(is_active=True)
        product_count = products.count()

        if product_count == 0:
            return {
                "product_count": 0,
                "average_rating": 0.0,
                "review_count": 0,
                "price_range": {"min": 0, "max": 0},
            }

        # Use aggregation for better performance
        stats = products.aggregate(
            avg_rating=Avg("average_rating"),
            total_reviews=models.Sum("rating_count"),
            min_price=models.Min("price"),
            max_price=models.Max("price"),
        )

        return {
            "product_count": product_count,
            "average_rating": float(stats["avg_rating"] or 0),
            "review_count": stats["total_reviews"] or 0,
            "price_range": {
                "min": float(stats["min_price"] or 0),
                "max": float(stats["max_price"] or 0),
            },
        }


# Additional utility model for brand management
class BrandRequest(BaseModel):
    """
    Model for users to request new brands to be added
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brand_requests",
    )
    brand_name = models.CharField(max_length=100)
    reason = models.TextField(help_text="Why should this brand be added?")
    website = models.URLField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    admin_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_brand_requests",
    )
    created_brand = models.OneToOneField(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brand_request",
    )

    class Meta:
        db_table = "product_brand_requests"
        ordering = ["-created_at"]
        verbose_name_plural = "Brand Requests"

    def __str__(self):
        return f"Request for {self.brand_name} by {self.requested_by.username}"


class BrandVariant(BaseModel):
    """
    Brand variants for different markets/languages
    Admin creates base variants, system can auto-generate others
    """

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="variants")
    template = models.ForeignKey(
        "BrandVariantTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variants",
        help_text="Template used to generate this variant",
    )
    name = models.CharField(max_length=100)  # Localized name
    language_code = models.CharField(max_length=10)  # ISO 639-1
    region_code = models.CharField(max_length=10, blank=True)  # ISO 3166-1
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to="brands/variants/", blank=True, null=True)

    # Variant-specific metadata
    local_website = models.URLField(blank=True)
    local_contact_email = models.EmailField(blank=True)
    local_social_media = models.JSONField(default=dict, blank=True)

    # Auto-generation flags
    is_auto_generated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Status
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ["brand", "language_code", "region_code"]
        db_table = "product_brand_variants"
        indexes = [
            models.Index(fields=["brand", "language_code"]),
            models.Index(fields=["language_code", "region_code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        region = f"-{self.region_code}" if self.region_code else ""
        return f"{self.brand.name} ({self.language_code}{region})"


class BrandVariantTemplate(BaseModel):
    """
    Templates for auto-generating variants based on market requirements
    """

    name = models.CharField(max_length=100, unique=True)
    language_code = models.CharField(max_length=10)
    region_code = models.CharField(max_length=10, blank=True)

    # Translation mappings
    name_translations = models.JSONField(
        default=dict, help_text="Common brand name translations for this locale"
    )

    # Default settings for this locale
    default_settings = models.JSONField(default=dict)

    # Auto-generation rules
    auto_generate_for_brands = models.BooleanField(default=False)
    brand_criteria = models.JSONField(
        default=dict,
        help_text="Criteria for auto-generating (e.g., min_products, countries)",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "product_brand_variant_templates"

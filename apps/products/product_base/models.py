from django.db import models
from django.conf import settings
from django.urls import reverse


from apps.core.models import BaseModel
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
    slug = models.SlugField(max_length=255, blank=True, db_index=True)
    short_code = models.CharField(
        max_length=200, unique=True, blank=True, null=True, db_index=True
    )

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")
    escrow_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    # Category and condition
    category = models.ForeignKey("categories.Category", on_delete=models.PROTECT)
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
    total_inventory = models.IntegerField(default=0)
    available_inventory = models.IntegerField(default=0)
    in_escrow_inventory = models.IntegerField(default=0)
    negotiable = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=12, choices=ProductsStatus.choices, default=ProductsStatus.DRAFT
    )

    # Product details and specifications - Updated to use Brand model
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    model = models.CharField(max_length=100, blank=True)
    material = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=50, blank=True)
    dimensions = models.CharField(max_length=100, blank=True)
    style = models.CharField(max_length=100, blank=True)
    authenticity_guaranteed = models.BooleanField(default=False)

    # Dynamic specifications field using JSONField
    specifications = models.JSONField(default=dict, blank=True)
    features = models.JSONField(default=list, blank=True)  # List of features

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

    def get_absolute_url(self):
        return reverse("product-detail", kwargs={"product_slug": self.slug})

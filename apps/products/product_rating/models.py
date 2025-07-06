from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel

User = get_user_model()


class ProductRating(BaseModel):
    """Individual product ratings from users"""

    product = models.ForeignKey(
        "product_base.Product",
        on_delete=models.CASCADE,
        related_name="ratings",
        db_index=True,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)], db_index=True
    )
    review = models.TextField(blank=True, null=True)
    title = models.CharField(max_length=200, blank=True, null=True)

    # Verification fields
    is_verified_purchase = models.BooleanField(default=False, db_index=True)
    purchase_date = models.DateTimeField(null=True, blank=True)

    # Moderation fields
    is_approved = models.BooleanField(default=True, db_index=True)
    is_flagged = models.BooleanField(default=False, db_index=True)
    flagged_reason = models.CharField(max_length=100, blank=True)

    # Helpfulness tracking
    helpful_count = models.PositiveIntegerField(default=0, db_index=True)
    total_votes = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "product_rating"
        unique_together = [["product", "user"]]  # One rating per user per product
        indexes = [
            models.Index(fields=["product", "is_approved", "-created_at"]),
            models.Index(fields=["rating", "is_approved"]),
            models.Index(fields=["is_verified_purchase", "is_approved"]),
            models.Index(fields=["-helpful_count", "is_approved"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.title} - {self.rating} stars by {self.user.username}"

    @property
    def helpfulness_ratio(self) -> float:
        if self.total_votes == 0:
            return 0.0
        return round((self.helpful_count / self.total_votes) * 100, 1)


class RatingHelpfulness(BaseModel):
    """Track if users find reviews helpful"""

    rating = models.ForeignKey(
        ProductRating, on_delete=models.CASCADE, related_name="helpfulness_votes"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_helpful = models.BooleanField()  # True = helpful, False = not helpful

    class Meta:
        db_table = "product_rating_help"
        unique_together = [["rating", "user"]]


class ProductRatingAggregate(BaseModel):
    """Cached rating aggregates for performance"""

    product = models.OneToOneField(
        "product_base.Product",
        on_delete=models.CASCADE,
        related_name="rating_aggregate",
    )

    # Aggregate data
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0, db_index=True
    )
    total_count = models.PositiveIntegerField(default=0, db_index=True)
    verified_count = models.PositiveIntegerField(default=0)

    # Rating breakdown
    stars_5_count = models.PositiveIntegerField(default=0)
    stars_4_count = models.PositiveIntegerField(default=0)
    stars_3_count = models.PositiveIntegerField(default=0)
    stars_2_count = models.PositiveIntegerField(default=0)
    stars_1_count = models.PositiveIntegerField(default=0)

    # Additional metrics
    has_reviews = models.BooleanField(default=False, db_index=True)
    last_rating_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "product_rating_aggregate"
        indexes = [
            models.Index(fields=["-average_rating", "total_count"]),
        ]

    @property
    def rating_breakdown(self) -> list[dict]:
        return [
            {"stars": 5, "count": self.stars_5_count},
            {"stars": 4, "count": self.stars_4_count},
            {"stars": 3, "count": self.stars_3_count},
            {"stars": 2, "count": self.stars_2_count},
            {"stars": 1, "count": self.stars_1_count},
        ]

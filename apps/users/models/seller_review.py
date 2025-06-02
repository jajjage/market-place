from django.db import models
from apps.core.models import BaseModel
from django.conf import settings


class SellerReview(BaseModel):
    REVIEW_TYPES = (
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("negative", "Negative"),
    )

    seller = models.ForeignKey(
        "users.UserProfile", on_delete=models.CASCADE, related_name="reviews"
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    review_type = models.CharField(max_length=10, choices=REVIEW_TYPES)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ("seller", "reviewer")

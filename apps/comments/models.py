from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from apps.core.models import BaseModel


class RatingEligibility(BaseModel):
    """Track rating eligibility for transactions"""

    transaction = models.OneToOneField(
        "transactions.EscrowTransaction",
        on_delete=models.CASCADE,
        related_name="rating_eligibility",
    )
    can_rate_from = models.DateTimeField()
    rating_deadline = models.DateTimeField()
    reminder_sent = models.BooleanField(default=False)
    final_reminder_sent = models.BooleanField(default=False)

    class Meta:
        db_table = "rating_eligibility"
        indexes = [
            models.Index(fields=["rating_deadline"]),
            models.Index(fields=["can_rate_from"]),
        ]

    def save(self, *args, **kwargs):
        if not self.can_rate_from:
            self.can_rate_from = self.transaction.status_changed_at
        if not self.rating_deadline:
            self.rating_deadline = self.transaction.status_changed_at + timedelta(
                days=30
            )
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        now = timezone.now()
        return self.can_rate_from <= now <= self.rating_deadline

    @property
    def days_remaining(self):
        if not self.is_active:
            return 0
        return max(0, (self.rating_deadline - timezone.now()).days)


# Update existing UserRating model
class UserRating(BaseModel):
    transaction = models.OneToOneField(
        "transactions.EscrowTransaction",
        on_delete=models.CASCADE,
        related_name="rating",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="given_ratings"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_ratings",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True, max_length=1000)
    is_verified = models.BooleanField(default=False)
    is_anonymous = models.BooleanField(default=False)  # Allow anonymous ratings

    # Admin moderation fields
    is_flagged = models.BooleanField(default=False)
    moderation_notes = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_ratings",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_ratings"
        ordering = ["-created_at"]
        unique_together = [
            ("from_user", "to_user", "transaction"),
        ]
        verbose_name = "User Rating"
        verbose_name_plural = "User Ratings"
        indexes = [
            models.Index(fields=["to_user", "-created_at"]),
            models.Index(fields=["from_user", "-created_at"]),
            models.Index(fields=["rating", "-created_at"]),
            models.Index(fields=["is_flagged"]),
        ]

    def clean(self):
        """Validate rating business rules"""
        # Validate user roles
        if self.from_user != self.transaction.buyer:
            raise ValidationError("Only buyers can rate sellers")

        if self.to_user != self.transaction.seller:
            raise ValidationError("Can only rate the transaction seller")

        # Check if rating period is active
        now = timezone.now()
        if hasattr(self.transaction, "rating_eligibility"):
            eligibility = self.transaction.rating_eligibility
            if not eligibility.is_active:
                raise ValidationError("Rating period is not active")

        # NEW: Check for duplicate rating on same transaction
        if self.pk is None:  # Only for new ratings (not updates)
            existing_rating = UserRating.objects.filter(
                from_user=self.from_user, transaction=self.transaction
            ).first()

            if existing_rating:
                raise ValidationError("You have already rated this transaction")

        if not self.transaction.status_changed_at:
            raise ValidationError("Transaction completion date is required")

        # Check 30-day rating window
        rating_deadline = self.transaction.status_changed_at + timedelta(days=30)
        if now > rating_deadline:
            raise ValidationError(
                "Rating period has expired (30 days after completion)"
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

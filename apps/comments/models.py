from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import BaseModel


class UserRating(BaseModel):
    """
    UserRating is a model representing a rating given by one user to another
    after a transaction. It includes the rating value, a comment, and
    references to the transaction and the users involved.
    """

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
    comment = models.TextField(blank=True)

    class Meta:
        # Ensure a user can only rate another user once per transaction
        db_table = "user_ratings"
        unique_together = ("from_user", "transaction")
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "transaction"], name="unique_rating"
            )
        ]

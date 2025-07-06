import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class DisputeReason(models.TextChoices):
    """
    An enumeration of possible reasons for a dispute.
    """

    NOT_AS_DESCRIBED = "not_as_described", _("Item Not As Described")
    NOT_RECEIVED = "not_received", _("Item Not Received")
    DAMAGED = "damaged", _("Item Damaged")
    WRONG_ITEM = "wrong_item", _("Wrong Item Received")
    OTHER = "other", _("Other")


class DisputeStatus(models.TextChoices):
    """
    An enumeration of possible statuses for a dispute.
    """

    OPENED = "opened", _("Opened")
    IN_REVIEW = "in_review", _("In Review")
    RESOLVED_BUYER = "resolved_buyer", _("Resolved for Buyer")
    RESOLVED_SELLER = "resolved_seller", _("Resolved for Seller")
    CLOSED = "closed", _("Closed")


class Dispute(BaseModel):
    """
    Represents a dispute raised for a transaction.

    A dispute can be opened by either the buyer or the seller for a transaction
    that has gone wrong. Each transaction can have at most one dispute.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(
        "transactions.EscrowTransaction",
        on_delete=models.CASCADE,
        related_name="dispute",
        help_text=_("The transaction under dispute"),
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="opened_disputes",
        help_text=_("User who opened this dispute"),
    )
    reason = models.CharField(
        max_length=30,
        choices=DisputeReason.choices,
        help_text=_("Why the dispute was raised"),
    )
    description = models.TextField(
        help_text=_("Details provided by the user opening the dispute")
    )
    status = models.CharField(
        max_length=20,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPENED,
        help_text=_("Current status of the dispute"),
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_disputes",
        help_text=_("Staff or moderator who resolved this dispute"),
    )
    resolution_note = models.TextField(
        blank=True,
        help_text=_("Notes on how dispute was resolved"),
    )

    class Meta:
        db_table = "disputes"
        verbose_name = _("Dispute")
        verbose_name_plural = _("Disputes")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["opened_by"]),
        ]

    def __str__(self):
        """
        Return a string representation of the dispute.
        """
        return (
            f"Dispute({self.transaction_id}) by {self.opened_by_id} "
            f"─ {self.get_reason_display()}"
        )

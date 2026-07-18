from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import BaseModel


class FundHold(BaseModel):
    """
    Represents a temporary lock placed on a portion of a seller's funds.
    Allows concurrent holds for different reasons.
    """

    HOLD_TYPE_TRANSACTION = "transaction_hold"
    HOLD_TYPE_DISPUTE = "dispute_hold"
    HOLD_TYPE_RESERVE = "reserve_hold"

    HOLD_TYPE_CHOICES = [
        (HOLD_TYPE_TRANSACTION, _("Transaction Hold")),
        (HOLD_TYPE_DISPUTE, _("Dispute Hold")),
        (HOLD_TYPE_RESERVE, _("Reserve Hold")),
    ]

    STATUS_ACTIVE = "active"
    STATUS_RELEASED = "released"
    STATUS_VOIDED = "voided"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Active")),
        (STATUS_RELEASED, _("Released")),
        (STATUS_VOIDED, _("Voided")),
    ]

    transaction = models.ForeignKey(
        "transactions.EscrowTransaction",
        on_delete=models.CASCADE,
        related_name="holds",
        null=True,
        blank=True,
        help_text=_("The transaction this hold is tied to"),
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="funds_holds",
        help_text=_("The seller whose funds are held"),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("The amount held"),
    )
    hold_type = models.CharField(
        max_length=30,
        choices=HOLD_TYPE_CHOICES,
        default=HOLD_TYPE_TRANSACTION,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    reason = models.TextField(
        blank=True,
        help_text=_("Explanation of why the hold was created"),
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When this hold was released/voided"),
    )

    class Meta:
        db_table = "escrow_funds_holds"
        verbose_name = _("Fund Hold")
        verbose_name_plural = _("Fund Holds")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "status"]),
            models.Index(fields=["transaction", "status"]),
        ]

    def __str__(self):
        return f"Hold #{self.id} ({self.get_hold_type_display()}) - {self.amount} - {self.status}"

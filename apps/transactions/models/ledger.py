from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.core.models import BaseModel


class SellerBalanceLedger(BaseModel):
    """
    Double-entry style log recording all credits and debits for a seller's balance.
    Allows running balance tracking and supports negative balances.
    """

    ENTRY_SALE_CREDIT = "sale_credit"
    ENTRY_PAYOUT_DEBIT = "payout_debit"
    ENTRY_PLATFORM_FEE = "platform_fee"
    ENTRY_REFUND_DEBIT = "refund_debit"
    ENTRY_CHARGEBACK_DEBIT = "chargeback_debit"
    ENTRY_ADJUSTMENT = "adjustment"

    ENTRY_TYPE_CHOICES = [
        (ENTRY_SALE_CREDIT, _("Sale Credit")),
        (ENTRY_PAYOUT_DEBIT, _("Payout Debit")),
        (ENTRY_PLATFORM_FEE, _("Platform Fee")),
        (ENTRY_REFUND_DEBIT, _("Refund Debit")),
        (ENTRY_CHARGEBACK_DEBIT, _("Chargeback Debit")),
        (ENTRY_ADJUSTMENT, _("Balance Adjustment")),
    ]

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        help_text=_("The seller account this entry relates to"),
    )
    transaction = models.ForeignKey(
        "transactions.EscrowTransaction",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        help_text=_("The related transaction (if applicable)"),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("The transaction amount (positive for credits, negative for debits)"),
    )
    entry_type = models.CharField(
        max_length=30,
        choices=ENTRY_TYPE_CHOICES,
        default=ENTRY_SALE_CREDIT,
    )
    description = models.TextField(
        blank=True,
        help_text=_("Explanation of the ledger adjustment"),
    )

    class Meta:
        db_table = "seller_balance_ledger"
        verbose_name = _("Seller Balance Ledger Entry")
        verbose_name_plural = _("Seller Balance Ledger Entries")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "created_at"]),
            models.Index(fields=["entry_type"]),
        ]

    def __str__(self):
        return f"Ledger #{self.id} for {self.seller.email} - {self.amount} ({self.entry_type})"

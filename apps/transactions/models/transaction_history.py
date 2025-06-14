from django.db import models
from django.urls import reverse
from django.conf import settings
from apps.core.models import BaseModel
from apps.transactions.models.transaction import EscrowTransaction


class TransactionHistory(BaseModel):
    """Tracks every status change in a transaction"""

    transaction = models.ForeignKey(
        EscrowTransaction, on_delete=models.CASCADE, related_name="history"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    previous_status = models.CharField(
        max_length=20, choices=EscrowTransaction.STATUS_CHOICES, null=True
    )
    new_status = models.CharField(
        max_length=20, choices=EscrowTransaction.STATUS_CHOICES
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        db_table = "transaction_history"
        verbose_name = "Transaction History"
        verbose_name_plural = "Transaction Histories"
        ordering = ["-timestamp"]
        unique_together = ("transaction", "timestamp")

    def __str__(self):
        return f"{self.transaction.id} changed to {self.status} at {self.timestamp}"

    def get_absolute_url(self):
        # This should return the URL for the transaction detail page
        return reverse("transactions:detail", kwargs={"transaction_id": self.id})

from django.conf import settings
from django.db import models

from .escrow_transactions import EscrowTransaction


class TransactionHistory(models.Model):
    """Tracks every status change in a transaction"""

    transaction = models.ForeignKey(
        EscrowTransaction, on_delete=models.CASCADE, related_name="history"
    )
    status = models.CharField(max_length=20, choices=EscrowTransaction.STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
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

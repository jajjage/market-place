from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from apps.core.models import BaseModel


class EscrowTransaction(BaseModel):
    """
    Represents an escrow transaction between a buyer and seller
    with the associated product and status
    """

    # Existing fields shown for context
    product = models.ForeignKey("product_base.Product", on_delete=models.PROTECT)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="buyer_transactions",
        on_delete=models.PROTECT,
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="seller_transactions",
        on_delete=models.PROTECT,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Status tracking
    STATUS_CHOICES = [
        ("initiated", "Initiated"),
        ("payment_received", "Payment Received"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("inspection", "In Inspection"),
        ("disputed", "Disputed"),
        ("completed", "Completed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
        ("funds_released", "Funds Released"),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="initiated"
    )

    # Tracking number info
    tracking_id = models.CharField(max_length=50, unique=True, db_index=True)
    tracking_number = models.CharField(
        max_length=100, blank=True, null=True, db_index=True
    )
    shipping_carrier = models.CharField(max_length=100, blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)

    # Inspection period
    inspection_period_days = models.PositiveSmallIntegerField(default=3)
    inspection_end_date = models.DateTimeField(blank=True, null=True)
    price_by_negotiation = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )

    # New fields for better automatic transition tracking
    status_changed_at = models.DateTimeField(default=timezone.now)
    is_auto_transition_scheduled = models.BooleanField(default=False)
    auto_transition_type = models.CharField(max_length=30, blank=True, null=True)
    next_auto_transition_at = models.DateTimeField(blank=True, null=True)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "escrow_transactions"
        verbose_name = "Escrow Transaction"
        verbose_name_plural = "Escrow Transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Escrow #{self.id} - {self.get_status_display()}"

    # -----------------------------------------------------------------------------
    # I may remove this in the future
    # -----------------------------------------------------------------------------
    def save(self, *args, **kwargs):
        # Track status change time
        if self.pk is not None:
            orig = EscrowTransaction.objects.get(pk=self.pk)
            if orig.status != self.status:
                self.status_changed_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_final_status(self):
        """Check if the transaction is in a final status"""
        return self.status in ["completed", "refunded", "cancelled"]

    @property
    def days_in_current_status(self):
        """Calculate how many days the transaction has been in its current status"""
        if self.status_changed_at:
            delta = timezone.now() - self.status_changed_at
            return delta.days
        return 0

    @property
    def time_until_auto_transition(self):
        """Calculate time remaining until the next automatic transition"""
        if (
            self.next_auto_transition_at
            and self.next_auto_transition_at > timezone.now()
        ):
            return self.next_auto_transition_at - timezone.now()
        return None


class TransactionHistory(BaseModel):
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

    def get_absolute_url(self):
        # This should return the URL for the transaction detail page
        return reverse("transactions:detail", kwargs={"transaction_id": self.id})

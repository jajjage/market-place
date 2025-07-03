from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.core.models import BaseModel


class EscrowTransaction(BaseModel):
    """
    Represents an escrow transaction between a buyer and seller
    with the associated product and status
    """

    STATUS_INITIATED = "initiated"
    STATUS_PAYMENT_RECEIVED = "payment_received"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_INSPECTION = "inspection"
    STATUS_DISPUTED = "disputed"
    STATUS_COMPLETED = "completed"
    STATUS_REFUNDED = "refunded"
    STATUS_CANCELLED = "cancelled"
    STATUS_FUNDS_RELEASED = "funds_released"

    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_PAYMENT_RECEIVED, "Payment Received"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_INSPECTION, "In Inspection"),
        (STATUS_DISPUTED, "Disputed"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_REFUNDED, "Refunded"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_FUNDS_RELEASED, "Funds Released"),
    ]

    # Existing fields shown for context
    product = models.ForeignKey(
        "product_base.Product",
        on_delete=models.PROTECT,
        related_name="escrow_transactions",
    )
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
    variant = models.ForeignKey(
        "product_variant.ProductVariant",
        on_delete=models.CASCADE,
        related_name="escrow_transactions",
        null=True,
        blank=True,
    )
    selected_options = models.JSONField(default=list, blank=True)
    quantity = models.IntegerField(default=1)
    currency = models.CharField(max_length=3, default="USD")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED
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
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

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
        indexes = [
            models.Index(fields=["tracking_id"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["buyer", "status"]),
            models.Index(fields=["seller", "status"]),
            models.Index(fields=["created_at", "status"]),
        ]

    def __str__(self):
        return f"Escrow #{self.id} - {self.product.title} ({self.status})"

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

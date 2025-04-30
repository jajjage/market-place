from django.db import models
from django.conf import settings
from apps.products.models import Product


class EscrowTransaction(models.Model):
    STATUS_CHOICES = [
        ("initiated", "Initiated"),
        ("payment_received", "Payment Received"),
        ("shipped", "Item Shipped"),
        ("delivered", "Item Delivered"),
        ("inspection", "In Inspection Period"),
        ("completed", "Completed"),
        ("disputed", "Disputed"),
        ("refunded", "Refunded"),
        ("cancelled", "Cancelled"),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="initiated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    inspection_period_days = models.PositiveSmallIntegerField(default=3)
    inspection_end_date = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_carrier = models.CharField(max_length=100, blank=True)
    shipping_address = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "escrow_transactions"
        verbose_name = "Escrow Transaction"
        verbose_name_plural = "Escrow Transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transaction {self.id}: {self.product.title} ({self.status})"

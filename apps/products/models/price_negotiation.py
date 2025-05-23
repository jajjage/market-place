from django.db import models
from django.conf import settings
from django.utils import timezone

from apps.core.models import BaseModel
from apps.transactions.models import EscrowTransaction


class PriceNegotiation(BaseModel):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("countered", "Countered"),
    )

    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="negotiations"
    )
    transaction = models.ForeignKey(
        EscrowTransaction,
        on_delete=models.CASCADE,
        related_name="negotiations",
        null=True,
        blank=True,
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="negotiations_as_buyer",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="negotiations_as_seller",
    )

    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    offered_price = models.DecimalField(max_digits=10, decimal_places=2)
    final_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    offered_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Negotiation #{self.id} - {self.product} - {self.status}"


class NegotiationHistory(BaseModel):
    ACTION_CHOICES = (
        ("price_offered", "Price Offered"),
        ("price_accepted", "Price Accepted"),
        ("price_rejected", "Price Rejected"),
        ("price_countered", "Price Countered"),
        ("price_updated", "Price Updated"),
    )

    negotiation = models.ForeignKey(
        PriceNegotiation, on_delete=models.CASCADE, related_name="history"
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Negotiation histories"

    def __str__(self):
        return f"{self.action} by {self.user} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

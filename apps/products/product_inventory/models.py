from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class InventoryTransaction(BaseModel):
    TRANSACTION_TYPES = (
        ("ADD", "Add to Total"),
        ("ACTIVATE", "Move to Available"),
        ("ESCROW", "Place in Escrow"),
        ("COMPLETE", "Complete Transaction"),
        ("CANCEL", "Cancel Escrow"),
    )

    product = models.ForeignKey(
        "product_base.Product",
        on_delete=models.CASCADE,
        related_name="inventory_transactions",
    )
    variant = models.ForeignKey(
        "product_variant.ProductVariant",
        on_delete=models.CASCADE,
        related_name="inventory_transactions",
        null=True,
        blank=True,
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    previous_total = models.IntegerField()
    previous_available = models.IntegerField()
    previous_in_escrow = models.IntegerField()
    new_total = models.IntegerField()
    new_available = models.IntegerField()
    new_in_escrow = models.IntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "product_inventory_transactions"
        ordering = ["-created_at"]
        verbose_name_plural = "Inventory Transactions"
        indexes = [
            models.Index(fields=["transaction_type"]),
            models.Index(fields=["product", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.transaction_type} - {self.product.title} ({self.quantity})"

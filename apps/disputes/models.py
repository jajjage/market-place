from django.conf import settings
from django.db import models
from apps.products.product_breadcrumb.models import Breadcrumb
from django.contrib.contenttypes.fields import GenericRelation

from apps.core.models import BaseModel


class Dispute(BaseModel):
    REASON_CHOICES = [
        ("not_as_described", "Item Not As Described"),
        ("not_received", "Item Not Received"),
        ("damaged", "Item Damaged"),
        ("wrong_item", "Wrong Item Received"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("opened", "Opened"),
        ("in_review", "In Review"),
        ("resolved_buyer", "Resolved for Buyer"),
        ("resolved_seller", "Resolved for Seller"),
        ("closed", "Closed"),
    ]

    transaction = models.OneToOneField(
        "transactions.EscrowTransaction",
        on_delete=models.CASCADE,
        related_name="dispute",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="opened_disputes",
    )
    breadcrumbs = GenericRelation(Breadcrumb)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="opened")

    class Meta:
        db_table = "disputes"
        verbose_name = "Dispute"
        verbose_name_plural = "Disputes"
        ordering = ["-created_at"]
        unique_together = ("transaction", "opened_by")

    def __str__(self):
        return f"Dispute for transaction {self.transaction.id}: {self.reason}"

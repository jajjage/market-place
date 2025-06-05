from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.core.models import (
    BaseModel,
)  # Assuming BaseModel provides id, created_at, updated_at


class Breadcrumb(BaseModel):
    # Foreign key to ContentType which defines the type of linked object (e.g., Product, Transaction, User)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # The ID of the specific object instance (e.g., product_id, transaction_id, user_id)
    object_id = models.PositiveIntegerField()
    # The GenericForeignKey itself, allowing access to the linked object
    content_object = GenericForeignKey("content_type", "object_id")

    # The breadcrumb segment details
    name = models.CharField(max_length=100)
    href = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    # Optional: A 'chain_type' or 'context' field to distinguish different breadcrumb *paths* for the same object
    # E.g., a 'Product' might have a 'product_detail_breadcrumb' and a 'related_products_breadcrumb' (though less common)
    # For an escrow platform, this could distinguish a 'transaction_flow' from a 'dispute_flow' linked to the same object ID if needed.
    # For now, let's assume one breadcrumb path per object, but keep it in mind.

    class Meta:
        ordering = ["order"]
        # Crucial index for efficient lookups on the generic foreign key
        indexes = [
            models.Index(fields=["content_type", "object_id", "order"]),
        ]

    def __str__(self):
        # Improved string representation to show the linked object
        return f"Breadcrumb for {self.content_object.__class__.__name__} #{self.object_id} - {self.name}"

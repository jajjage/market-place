from django.db import models
from apps.core.models import BaseModel


class Breadcrumb(BaseModel):
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="breadcrumbs"
    )
    name = models.CharField(max_length=100)
    href = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        indexes = [
            models.Index(fields=["product", "order"]),
        ]

    def __str__(self):
        return f"{self.product.title} - {self.name}"

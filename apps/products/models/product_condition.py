from django.db import models
from apps.core.models import BaseModel


class ProductCondition(BaseModel):
    name = models.CharField(max_length=50)  # New, Like New, Good, Fair, etc.
    description = models.TextField(blank=True)

    class Meta:
        db_table = "product_conditions"
        verbose_name_plural = "Product Conditions"
        ordering = ["name"]

    def __str__(self):
        return self.name

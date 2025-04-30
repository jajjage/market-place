from django.db import models

from apps.core.models import BaseModel


class ProductImage(BaseModel):
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="product_images/")
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "product_images"
        ordering = ["display_order"]
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"Image for {self.product.title}"

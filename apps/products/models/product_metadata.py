from django.db import models


from apps.core.models import BaseModel


class ProductMeta(BaseModel):
    """For additional product metadata that isn't part of specifications"""

    product = models.OneToOneField(
        "Product", on_delete=models.CASCADE, related_name="meta"
    )
    views_count = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    seo_keywords = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "product_meta"
        verbose_name_plural = "Product Meta"
        ordering = ["-views_count"]

    def __str__(self):
        return f"Meta for {self.product.title}"

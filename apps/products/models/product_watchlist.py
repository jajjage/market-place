from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class ProductWatchlistItem(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlist"
    )
    product = models.ForeignKey(
        "Product", on_delete=models.CASCADE, related_name="watchers"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_watchlist_items"
        unique_together = ("user", "product")
        indexes = [
            models.Index(fields=["user", "product"]),
            models.Index(fields=["product", "added_at"]),
            models.Index(fields=["added_at"]),
        ]

    def __str__(self):
        return f"{self.user.first_name} watching {self.product.title}"

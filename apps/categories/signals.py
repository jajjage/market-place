from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.categories.models import Category
from apps.categories.services import CategoryService
from apps.core.utils.cache_manager import CacheManager


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_breadcrumb_cache(sender, instance, **kwargs):
    """Invalidate category breadcrumb cache when category changes."""
    CategoryService.invalidate_breadcrumb_cache(instance.id)

    # Also invalidate breadcrumb cache for all products in this category
    if hasattr(instance, "products"):
        for product in instance.products.all():
            CacheManager.invalidate("breadcrumb", object_id=product.pk)

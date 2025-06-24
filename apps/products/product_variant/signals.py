import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.utils.cache_manager import CacheManager
from apps.products.product_variant.models import (
    ProductVariantOption,
    ProductVariantType,
)

logger = logging.getLogger("variant_performance")


@receiver(post_save, sender=ProductVariantType)
def invalidate_types_cache_on_save(sender, instance, **kwargs):
    """Enhanced cache invalidation on product deletion."""

    def invalidate_caches():
        CacheManager.invalidate_key(
            "product_variant", "types", active_only=True, with_options=True
        )
        logger.info(f"Cache invalidated for deleted product variant: {instance.id}")

    transaction.on_commit(invalidate_caches)


@receiver(post_save, sender=ProductVariantOption)
def invalidate_options_cache_on_save(sender, instance, **kwargs):
    """Enhanced cache invalidation on product deletion."""

    def invalidate_caches():
        CacheManager.invalidate_key(
            "product_variant", "types", active_only=True, with_options=True
        )
        logger.info(f"Cache invalidated for deleted product variant: {instance.id}")

    transaction.on_commit(invalidate_caches)

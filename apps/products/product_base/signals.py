import logging
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.products.product_base.models import Product
from apps.products.product_base.services.product_detail_service import (
    ProductDetailService,
)
from apps.products.product_base.services.product_list_service import ProductListService
from apps.products.product_variant.services import ProductVariantService


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def invalidate_product_cache_on_save(sender, instance, created, **kwargs):
    """Enhanced signal handler with transaction safety"""

    def invalidate_caches():
        logger.info("=== CACHE INVALIDATION TRIGGERED ===")
        logger.info(f"Product: {instance.short_code}, Created: {created}")

        if not created:
            ProductDetailService.invalidate_product_cache(instance.short_code)
            logger.info(f"Invalidated detail cache for product {instance.short_code}")

        ProductListService.invalidate_product_list_caches()
        logger.info(f"Cache invalidation completed for product: {instance.short_code}")

    # Only invalidate after transaction commits
    transaction.on_commit(invalidate_caches)


@receiver(post_delete, sender=Product)
def invalidate_product_cache_on_delete(sender, instance, **kwargs):
    """Enhanced cache invalidation on product deletion."""

    def invalidate_caches():
        ProductListService.invalidate_product_list_caches()
        logger.info(f"Cache invalidated for deleted product: {instance.short_code}")

    transaction.on_commit(invalidate_caches)


@receiver(post_save, sender="product_variant.ProductVariant")
def invalidate_product_cache_on_variant_change(sender, instance, created, **kwargs):
    """Invalidate cache when product variants change."""

    def invalidate_caches():
        if hasattr(instance, "product"):
            ProductListService.invalidate_product_list_caches()
            if not created:
                # Invalidate both detail and list caches
                ProductDetailService.invalidate_product_cache(
                    instance.product.short_code
                )

            ProductVariantService.invalidate_variant_detail_caches()
            logger.info(
                f"Cache invalidated for product {instance.product.short_code} due to variant change"
            )

    transaction.on_commit(invalidate_caches)


@receiver(post_delete, sender="product_variant.ProductVariant")
def invalidate_product_cache_on_variant_delete(sender, instance, **kwargs):
    """Invalidate cache when a product variant is deleted."""

    def invalidate_caches():
        if hasattr(instance, "product"):
            # Invalidate both detail and list caches
            ProductDetailService.invalidate_product_cache(instance.product.short_code)
            ProductListService.invalidate_product_list_caches(instance.product)
            logger.info(
                f"Cache invalidated for product {instance.product.short_code} due to variant deletion"
            )

    transaction.on_commit(invalidate_caches)

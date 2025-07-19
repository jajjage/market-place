import logging
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.products.product_base.services.product_detail_service import (
    ProductDetailService,
)
from apps.products.product_metadata.tasks import generate_seo_keywords_for_product


logger = logging.getLogger(__name__)


print("🔥 SIGNALS MODULE IMPORTED 🔥")


@receiver(
    post_save, sender="product_base.Product"
)  # Use string reference instead of model import
def invalidate_product_cache_on_save(sender, instance, created, **kwargs):
    """
    Enhanced signal handler with transaction safety.
    For high-traffic sites, use the async version:
    ProductCacheInvalidationService.invalidate_all_product_caches_async()
    """

    def invalidate_caches():
        logger.info("=== CACHE INVALIDATION TRIGGERED ===")
        logger.info(f"Product: {instance.short_code}, Created: {created}")
        if created:
            result = generate_seo_keywords_for_product.delay(instance.id)

            if result.successful:
                logger.info(f"SEO generation task for product: {instance.title}")

        if not created:
            # Import here to avoid circular imports
            from .services import ProductDetailService

            ProductDetailService.invalidate_product_cache(instance.short_code)
            logger.info(f"Invalidated detail cache for product {instance.short_code}")

        # Import here to avoid circular imports
        from apps.products.product_base.services.product_list_service import (
            ProductCacheInvalidationService,
        )

        ProductCacheInvalidationService.invalidate_all_product_caches()
        logger.info(f"Cache invalidation completed for product: {instance.short_code}")

    # Only invalidate after transaction commits
    transaction.on_commit(invalidate_caches)


@receiver(post_delete, sender="product_base.Product")
def invalidate_product_cache_on_delete(sender, instance, **kwargs):
    """Handle product deletion cache invalidation"""

    def invalidate_caches():
        logger.info("=== PRODUCT DELETED - CACHE INVALIDATION ===")
        logger.info(f"Product: {instance.short_code}")

        from .services import ProductDetailService
        from apps.products.product_base.services.product_list_service import (
            ProductCacheInvalidationService,
        )

        ProductDetailService.invalidate_product_cache(instance.short_code)
        ProductCacheInvalidationService.invalidate_all_product_caches()
        logger.info(
            f"Cache invalidation completed for deleted product: {instance.short_code}"
        )

    transaction.on_commit(invalidate_caches)


@receiver([post_save, post_delete], sender="product_variant.ProductVariant")
def invalidate_product_cache_on_variant_change(sender, instance, created, **kwargs):
    """Invalidate cache when product variants change."""

    def invalidate_caches():
        if hasattr(instance, "product"):
            from .services import ProductDetailService
            from apps.products.product_variant.services import ProductVariantService
            from apps.products.product_base.services.product_list_service import (
                ProductCacheInvalidationService,
            )

            ProductCacheInvalidationService.invalidate_all_product_caches()
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


# DEBUGGING FUNCTIONS - Add these temporarily to test if signals work at all
@receiver(post_save)
def debug_all_post_save_signals(sender, **kwargs):
    """Debug signal - logs ALL post_save signals"""
    logger.info(f"🔍 DEBUG: post_save signal fired for {sender}")
    print(f"🔍 DEBUG: post_save signal fired for {sender}")


@receiver(post_save, sender="product_base.Product")
def debug_product_signal(sender, instance, **kwargs):
    """Debug signal specifically for Product model"""
    logger.info(f"🎯 DEBUG: Product signal fired for {instance}")
    print(f"🎯 DEBUG: Product signal fired for {instance}")


# Signal Connection Verification
def verify_signal_connections():
    """Call this in Django shell to verify signals are connected"""
    from django.db.models.signals import post_save, post_delete

    print("=== SIGNAL CONNECTIONS ===")
    print("post_save receivers:")
    for recv in post_save.receivers:
        print(f"  - {recv}")

    print("post_delete receivers:")
    for recv in post_delete.receivers:
        print(f"  - {recv}")

    return True


@receiver(post_delete, sender="product_variant.ProductVariant")
def invalidate_product_cache_on_variant_delete(sender, instance, **kwargs):
    """Invalidate cache when a product variant is deleted."""

    def invalidate_caches():
        if hasattr(instance, "product"):
            # Invalidate both detail and list caches
            from apps.products.product_base.services.product_list_service import (
                ProductCacheInvalidationService,
            )

            ProductDetailService.invalidate_product_cache(instance.product.short_code)
            ProductCacheInvalidationService.invalidate_product_caches(
                product_instance=instance.product
            )
            logger.info(
                f"Cache invalidated for product {instance.product.short_code} due to variant deletion"
            )

    transaction.on_commit(invalidate_caches)

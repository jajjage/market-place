import logging
from django.db import transaction
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from apps.products.product_base.models import Product
from apps.products.product_base.services.product_detail_service import (
    ProductDetailService,
)
from apps.products.product_base.services.product_list_service import ProductListService
from apps.products.product_base.utils.social_sharing import (
    create_unique_short_code,
    generate_seo_friendly_slug,
)

# from apps.products.product_breadcrumb.services import BreadcrumbService
from apps.products.product_metadata.models import ProductMeta

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Product)
def ensure_product_slug_and_shortcode(sender, instance, **kwargs):
    """
    Ensure product has slug and short_code before saving.
    This is a pre_save signal that automatically generates:
    1. A URL-friendly slug based on the product title
    2. A short code for social media sharing
    """
    # Generate slug if:
    # 1. Product is new (no pk) OR
    # 2. Title has changed OR
    # 3. Slug is empty
    short_code = ""
    slug = ""
    title_changed = False
    # Check if the instance already exists and if the title has changed
    if instance.pk:
        try:
            old = Product.objects.get(pk=instance.pk)
            title_changed = old.title != instance.title
        except Product.DoesNotExist:
            title_changed = False
    else:
        title_changed = False

    should_generate_slug = (
        not instance.pk  # New object
        or title_changed  # Title changed on update
        or not instance.slug  # Slug is missing
    )

    # If short_code doesn't exist, create one
    if should_generate_slug and instance.title:
        logger.info(f"Generating slug for product '{instance.title}'")
        slug = generate_seo_friendly_slug(instance.title)
        instance.slug = slug
        logger.info(f"Generated slug: {instance.slug}")

    if not instance.short_code:
        logger.info("Generating short code for product")
        short_code = create_unique_short_code(Product)
        instance.short_code = f"{slug}-{short_code}"
        logger.info(f"Generated short code: {instance.short_code}")


@receiver(post_save, sender=Product)
def ensure_product_meta(sender, instance, created, **kwargs):
    """
    Ensure product has associated meta information.
    This is a post_save signal that automatically creates a ProductMeta
    object if one doesn't exist.
    """
    if not hasattr(instance, "meta") or not instance.meta:
        # Create meta object for tracking social shares, views, etc.
        ProductMeta.objects.create(
            product=instance,
            views_count=0,
            total_shares=0,
            featured=False,
            seo_keywords=instance.slug or "",
        )


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
def invalidate_product_cache_on_variant_change(sender, instance, **kwargs):
    """Invalidate cache when product variants change."""

    def invalidate_caches():
        if hasattr(instance, "product"):
            # Invalidate both detail and list caches
            ProductDetailService.invalidate_product_cache(instance.product.short_code)
            ProductListService.invalidate_product_list_caches(instance.product)
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

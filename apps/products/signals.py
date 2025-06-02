from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import logging
from .models import Product, ProductMeta
from .utils.social_sharing_utils import (
    create_unique_short_code,
    generate_seo_friendly_slug,
)

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
    should_generate_slug = (
        not instance.pk  # New product
        or (
            instance.pk
            and Product.objects.filter(pk=instance.pk)
            .exclude(title=instance.title)
            .exists()
        )  # Title changed
        or not instance.slug  # Empty slug
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

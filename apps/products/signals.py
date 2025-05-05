from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Product, ProductMeta
from .utils.social_sharing_utils import (
    create_unique_short_code,
    generate_seo_friendly_slug,
)


@receiver(pre_save, sender=Product)
def ensure_product_slug_and_shortcode(sender, instance, **kwargs):
    """
    Ensure product has slug and short_code before saving.
    This is a pre_save signal that automatically generates:
    1. A URL-friendly slug based on the product title
    2. A short code for social media sharing
    """
    # If this is a new product (no ID yet) or title has changed, update the slug
    if (
        not instance.pk
        or Product.objects.filter(pk=instance.pk).exclude(title=instance.title).exists()
    ):
        if instance.title:  # Only generate if title exists
            instance.slug = generate_seo_friendly_slug(instance.title)

    # If short_code doesn't exist, create one
    if not instance.short_code:
        instance.short_code = create_unique_short_code(Product)


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

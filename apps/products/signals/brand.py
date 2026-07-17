from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
import logging
from apps.products.models import Brand
from apps.products.documents import BrandDocument
from apps.products.tasks import auto_generate_brand_variants

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Brand)
def update_brand_document(sender, instance, **kwargs):
    """Update Elasticsearch document when Brand is saved"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = BrandDocument.get(id=instance.id)
        doc.update(instance)
    except:
        # Document doesn't exist, create it
        try:
            BrandDocument().update(instance)
        except:
            pass


@receiver(post_delete, sender=Brand)
def delete_brand_document(sender, instance, **kwargs):
    """Delete Elasticsearch document when Brand is deleted"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = BrandDocument.get(id=instance.id)
        doc.delete()
    except:
        pass  # Document doesn't exist


@receiver(post_save, sender=Brand)
def trigger_variant_auto_generation(sender, instance, created, **kwargs):
    """
    Trigger auto-generation of brand variants when a brand is created or updated

    Args:
        sender: Brand model
        instance: Brand instance
        created: Boolean indicating if this is a new instance
        **kwargs: Additional arguments
    """
    if getattr(settings, "TESTING", False):
        return

    if created and instance.is_active:
        # Delay the task to avoid blocking the main request
        auto_generate_brand_variants.delay(instance.id)
        logger.info(
            f"Triggered auto-generation for brand {instance.name} (ID: {instance.id})"
        )

    elif not created and instance.is_active:
        # For updates, you might want to regenerate variants
        # Be careful not to overwrite manually created variants
        # You could add a flag to control this behavior
        pass

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging
from .models import Brand
from .documents import BrandDocument
from .tasks import auto_generate_brand_variants

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Brand)
def update_brand_document(sender, instance, **kwargs):
    """Update Elasticsearch document when Brand is saved"""
    try:
        doc = BrandDocument.get(id=instance.id)
        doc.update(instance)
    except:
        # Document doesn't exist, create it
        BrandDocument().update(instance)


@receiver(post_delete, sender=Brand)
def delete_brand_document(sender, instance, **kwargs):
    """Delete Elasticsearch document when Brand is deleted"""
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

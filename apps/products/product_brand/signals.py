from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Brand
from .documents import BrandDocument


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

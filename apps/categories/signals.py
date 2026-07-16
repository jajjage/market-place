from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings

from apps.categories.documents import CategoryDocument
from apps.categories.models import Category


@receiver(post_save, sender=Category)
def update_category_document(sender, instance, **kwargs):
    """Update Elasticsearch document when Category is saved"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = CategoryDocument.get(id=instance.id)
        doc.update(instance)
    except:
        # Document doesn't exist, create it
        try:
            CategoryDocument().update(instance)
        except:
            pass


@receiver(post_delete, sender=Category)
def delete_category_document(sender, instance, **kwargs):
    """Delete Elasticsearch document when Category is deleted"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = CategoryDocument.get(id=instance.id)
        doc.delete()
    except:
        pass  # Document doesn't exist


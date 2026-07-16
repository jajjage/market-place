from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from apps.products.models import Product
from apps.products.models import ProductMeta
from apps.products.documents import ProductDocument


@receiver(post_save, sender=Product)
def update_product_document(sender, instance, **kwargs):
    """Update Elasticsearch document when Product is saved"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = ProductDocument.get(id=instance.id)
        doc.update(instance)
    except:
        # Document doesn't exist, create it
        try:
            ProductDocument().update(instance)
        except:
            pass


@receiver(post_delete, sender=Product)
def delete_product_document(sender, instance, **kwargs):
    """Delete Elasticsearch document when Product is deleted"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = ProductDocument.get(id=instance.id)
        doc.delete()
    except:
        pass  # Document doesn't exist


@receiver(post_save, sender=ProductMeta)
def update_product_document_on_meta_change(sender, instance, **kwargs):
    """Update product document when metadata changes"""
    if getattr(settings, "TESTING", False):
        return
    try:
        doc = ProductDocument.get(id=instance.product.id)
        doc.update(instance.product)
    except:
        pass  # Document doesn't exist

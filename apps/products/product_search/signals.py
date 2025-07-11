from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.products.product_base.models import Product
from apps.products.product_metadata.models import ProductMeta
from apps.products.product_search.documents import ProductDocument


@receiver(post_save, sender=Product)
def update_product_document(sender, instance, **kwargs):
    """Update Elasticsearch document when Product is saved"""
    try:
        doc = ProductDocument.get(id=instance.id)
        doc.update(instance)
    except:
        # Document doesn't exist, create it
        ProductDocument().update(instance)


@receiver(post_delete, sender=Product)
def delete_product_document(sender, instance, **kwargs):
    """Delete Elasticsearch document when Product is deleted"""
    try:
        doc = ProductDocument.get(id=instance.id)
        doc.delete()
    except:
        pass  # Document doesn't exist


@receiver(post_save, sender=ProductMeta)
def update_product_document_on_meta_change(sender, instance, **kwargs):
    """Update product document when metadata changes"""
    try:
        doc = ProductDocument.get(id=instance.product.id)
        doc.update(instance.product)
    except:
        pass  # Document doesn't exist

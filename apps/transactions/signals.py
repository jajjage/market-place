from django.db.models.signals import pre_save
from django.dispatch import receiver
from apps.transactions.models import EscrowTransaction


@receiver(pre_save, sender=EscrowTransaction)
def ensure_tracking_id(sender, instance, **kwargs):
    """
    Signal to ensure every EscrowTransaction has a tracking_id
    """
    if (
        not instance.tracking_id
        and instance.product
        and instance.buyer
        and instance.seller
    ):
        from apps.products.services.inventory import InventoryService

        instance.tracking_id = InventoryService.generate_tracking_id(
            instance.product, instance.buyer, instance.seller
        )

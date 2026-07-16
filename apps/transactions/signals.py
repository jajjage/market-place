from datetime import timedelta
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from django.utils import timezone
from django.conf import settings

from apps.transactions.models import EscrowTransaction

from apps.transactions.tasks.transitions_tasks import (
    schedule_auto_inspection,
    schedule_auto_completion,
)

from apps.notifications.tasks import send_status_change_notification
from apps.transactions.utils.tracking_id import generate_tracking_id

# Define default grace periods if not in settings
DEFAULT_DELIVERY_GRACE_PERIOD = 3  # days
DEFAULT_AUTO_REFUND_PERIOD = 14  # days


@receiver(post_save, sender=EscrowTransaction)
def invalidate_transaction_caches(sender, instance, created, **kwargs):
    """
    Invalidate caches related to the transaction
    This should be called whenever a transaction is updated
    """
    from apps.transactions.services.transaction_list_service import (
        TransactionListService,
    )
    TransactionListService.invalidate_all_caches_for_transaction(instance)





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

        instance.tracking_id = generate_tracking_id(
            instance.product, instance.buyer, instance.seller
        )


@receiver(post_save, sender=EscrowTransaction)
def update_product_inventory(sender, instance, created, **kwargs):
    """
    Signal to update product inventory when a transaction is created, cancelled, or completed
    """
    if not instance.variant:
        return

    if created:
        instance.variant.reserve_stock(instance.quantity)
    elif instance.status == "cancelled":
        instance.variant.release_stock(instance.quantity)
    elif instance.status == "completed":
        instance.variant.reduce_stock(instance.quantity)


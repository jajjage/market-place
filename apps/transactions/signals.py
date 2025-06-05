from datetime import timedelta
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from apps.products.product_breadcrumb.services import (
    BreadcrumbService,
)
from apps.transactions.models import EscrowTransaction
from apps.transactions.tasks.transitions_tasks import (
    schedule_auto_inspection,
    schedule_auto_completion,
)

from apps.notifications.tasks import send_status_change_notification

# Define default grace periods if not in settings
DEFAULT_DELIVERY_GRACE_PERIOD = 3  # days
DEFAULT_AUTO_REFUND_PERIOD = 14  # days


# Store original status before save for comparison
@receiver(pre_save, sender=EscrowTransaction)
def store_original_status(sender, instance, **kwargs):
    """Store the original status before save for comparison after save"""
    if instance.pk:
        try:
            instance._original_status = EscrowTransaction.objects.get(
                pk=instance.pk
            ).status
        except EscrowTransaction.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None


@receiver(post_save, sender=EscrowTransaction)
def handle_escrow_status_changes(sender, instance, created, **kwargs):
    """
    Signal handler for escrow transaction status changes
    Schedules appropriate automatic transitions based on status
    """
    transaction_id = instance.id
    current_status = instance.status

    # For new transactions, just record creation
    if created:
        # Set initial values for auto-transition tracking
        instance.status_changed_at = timezone.now()
        instance.is_auto_transition_scheduled = False
        instance.save(
            update_fields=["status_changed_at", "is_auto_transition_scheduled"]
        )
        return

    # Only process further if status field was updated
    if (
        not hasattr(instance, "_original_status")
        or instance._original_status == current_status
    ):
        return

    # Get the old status for notifications
    old_status = instance._original_status

    # Handle delivered status - schedule auto transition to inspection after grace period
    if current_status == "delivered":
        # Get grace period from settings or use default
        grace_period_days = getattr(
            settings, "DELIVERY_GRACE_PERIOD_DAYS", DEFAULT_DELIVERY_GRACE_PERIOD
        )
        next_transition_time = timezone.now() + timedelta(days=grace_period_days)

        # Update tracking fields
        instance.is_auto_transition_scheduled = True
        instance.auto_transition_type = "inspection"
        instance.next_auto_transition_at = next_transition_time
        instance.save(
            update_fields=[
                "is_auto_transition_scheduled",
                "auto_transition_type",
                "next_auto_transition_at",
            ]
        )

        # Schedule the auto-inspection task
        schedule_auto_inspection.apply_async(
            args=[transaction_id],
            countdown=grace_period_days * 86400,  # Convert days to seconds
        )

    # Handle inspection status - schedule auto completion after inspection period
    elif current_status == "inspection":
        if instance.inspection_end_date:
            # Calculate seconds until inspection period ends
            time_remaining = (
                instance.inspection_end_date - timezone.now()
            ).total_seconds()

            # Update tracking fields
            instance.is_auto_transition_scheduled = True
            instance.auto_transition_type = "completed"
            instance.next_auto_transition_at = instance.inspection_end_date
            instance.save(
                update_fields=[
                    "is_auto_transition_scheduled",
                    "auto_transition_type",
                    "next_auto_transition_at",
                ]
            )

            # Schedule the auto-completion task to run when inspection period ends
            schedule_auto_completion.apply_async(
                args=[transaction_id],
                countdown=max(
                    0, time_remaining
                ),  # Ensure we don't schedule negative time
            )

    # Handle disputed status - schedule auto-refund after long inactivity
    elif current_status == "disputed":
        # Auto-refund after long period if dispute isn't resolved
        refund_period_days = getattr(
            settings, "DISPUTE_AUTO_REFUND_DAYS", DEFAULT_AUTO_REFUND_PERIOD
        )
        next_transition_time = timezone.now() + timedelta(days=refund_period_days)

        # Update tracking fields
        instance.is_auto_transition_scheduled = True
        instance.auto_transition_type = "refunded"
        instance.next_auto_transition_at = next_transition_time
        instance.save(
            update_fields=[
                "is_auto_transition_scheduled",
                "auto_transition_type",
                "next_auto_transition_at",
            ]
        )

        from apps.transactions.tasks.transitions_tasks import (
            auto_refund_disputed_transaction,
        )

        auto_refund_disputed_transaction.apply_async(
            args=[transaction_id],
            countdown=refund_period_days * 86400,  # Convert days to seconds
        )

    # For final statuses, clear auto-transition flags
    elif current_status in ["completed", "refunded", "cancelled"]:
        instance.is_auto_transition_scheduled = False
        instance.auto_transition_type = None
        instance.next_auto_transition_at = None
        instance.save(
            update_fields=[
                "is_auto_transition_scheduled",
                "auto_transition_type",
                "next_auto_transition_at",
            ]
        )

    # Send notification about status change
    # Determine if this was an automatic change (could be enhanced further)
    is_automatic = kwargs.get("auto_transition", False)
    send_status_change_notification.apply_async


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
        from apps.products.product_inventory.services import InventoryService

        instance.tracking_id = InventoryService.generate_tracking_id(
            instance.product, instance.buyer, instance.seller
        )


@receiver(post_save, sender=EscrowTransaction)
def create_or_update_transaction_breadcrumbs(sender, instance, created, **kwargs):
    """
    Signal handler to generate/update breadcrumbs for a Transaction.
    """
    # This ensures that breadcrumbs are generated when a transaction is created
    # or when its main details are updated (if needed).
    # You might want to refine when this is called based on what triggers a "main" breadcrumb path change.
    BreadcrumbService.generate_breadcrumbs_for_transaction(instance)
    # You'd have similar signals for Product, Dispute, UserProfile, etc

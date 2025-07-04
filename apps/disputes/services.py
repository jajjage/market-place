from django.db import transaction
from django.db.models import Count, Q
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.transactions.services.transaction_list_service import TransactionListService
from .models import Dispute, DisputeStatus
from apps.notifications.services.notification_service import NotificationService
from .tasks import (
    update_transaction_status,
)
import logging

logger = logging.getLogger("dispute_performance")


class DisputeService:
    """Service class for dispute business logic"""

    CACHE_TTL = 60 * 15

    @staticmethod
    def create_dispute(transaction_id, user, reason, description):
        """Create a new dispute with proper validations and notifications"""
        start_time = timezone.now()

        # Get transaction object
        from apps.transactions.models import EscrowTransaction

        try:
            transaction_obj = EscrowTransaction.objects.get(id=transaction_id)
        except EscrowTransaction.DoesNotExist:
            raise ValidationError("Transaction not found")

        with transaction.atomic():
            # Check if dispute already exists
            if hasattr(transaction_obj, "dispute"):
                raise ValidationError("A dispute already exists for this transaction")

            # Validate user can dispute
            if user not in [transaction_obj.buyer, transaction_obj.seller]:
                raise ValidationError("You can only dispute your own transactions")

            # Check transaction status - disputes can only be opened for specific states
            DISPUTABLE_STATUSES = ["inspection", "completed", "funds_released"]
            if transaction_obj.status not in DISPUTABLE_STATUSES:
                raise ValidationError(
                    f"Disputes can only be opened for transactions in inspection, completed, or funds_released status. "
                    f"Current status: {transaction_obj.get_status_display()}"
                )

            # Create dispute
            dispute = Dispute.objects.create(
                transaction=transaction_obj,
                opened_by=user,
                reason=reason,
                description=description,
                status=DisputeStatus.OPENED,
            )

            # Update transaction status to disputed
            update_transaction_status.delay(transaction_obj.id, "disputed")

            # Send notifications
            recipient = dispute.get_other_party()
            if recipient:
                NotificationService.send_notification(
                    recipient, "new_dispute", {"dispute_id": dispute.id}
                )

            # Invalidate cache
            CacheManager.invalidate("dispute", transaction_id=transaction_obj.id)
            TransactionListService.invalidate_user_transaction_caches(user.id)

            duration = (timezone.now() - start_time).total_seconds() * 1000
            logger.info(f"Created dispute {dispute.id} in {duration:.2f}ms")

            return dispute

    @staticmethod
    def resolve_dispute(dispute_id, resolver_user, status, resolution_note):
        """Resolve a dispute with proper status updates"""
        start_time = timezone.now()

        with transaction.atomic():
            dispute = Dispute.objects.select_for_update().get(id=dispute_id)

            # Validate current status
            if dispute.status in [
                DisputeStatus.RESOLVED_BUYER,
                DisputeStatus.RESOLVED_SELLER,
                DisputeStatus.CLOSED,
            ]:
                raise ValidationError("Dispute is already resolved")

            # Update dispute
            dispute.status = status
            dispute.resolved_by = resolver_user
            dispute.resolution_note = resolution_note
            dispute.save()

            # Update transaction based on resolution
            if status == DisputeStatus.RESOLVED_BUYER:
                update_transaction_status.delay(dispute.transaction.id, "refunded")
            elif status == DisputeStatus.RESOLVED_SELLER:
                update_transaction_status.delay(dispute.transaction.id, "completed")

            # Send notifications
            NotificationService.send_notification(
                dispute.opened_by,
                "dispute_resolved",
                {"dispute_id": dispute.id, "status": status},
            )
            NotificationService.send_notification(
                dispute.get_other_party(),
                "dispute_resolved",
                {"dispute_id": dispute.id, "status": status},
            )

            # Invalidate cache
            CacheManager.invalidate_key("dispute", "detail", id=dispute.id)
            TransactionListService.invalidate_user_transaction_caches(
                dispute.opened_by.id
            )

            duration = (timezone.now() - start_time).total_seconds() * 1000
            logger.info(f"Resolved dispute {dispute.id} in {duration:.2f}ms")

            return dispute

    @staticmethod
    def get_user_disputes(user, status=None):
        """Get disputes for a user with caching"""
        cache_key = CacheKeyManager.make_key(
            "dispute", "user_list", user_id=user.id, status=status or "all"
        )

        # Try cache first
        from django.core.cache import cache

        cached_disputes = cache.get(cache_key)
        if cached_disputes is not None:
            logger.info(f"Retrieved user disputes from cache for user {user.id}")
            return cached_disputes

        start_time = timezone.now()

        # Build query
        from django.db.models import Q

        queryset = Dispute.objects.filter(
            Q(transaction__buyer=user) | Q(transaction__seller=user)
        ).select_related("opened_by", "resolved_by", "transaction")

        if status:
            queryset = queryset.filter(status=status)

        disputes = list(queryset.order_by("-created_at"))

        # Cache for 5 minutes
        cache.set(cache_key, disputes, 300)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Retrieved {len(disputes)} user disputes in {duration:.2f}ms")

        return disputes

    @staticmethod
    def get_stats(user):
        """Return dispute stats dict for staff users, cached."""
        if not user.is_staff:
            raise PermissionError("Only staff can view statistics")

        cache_key = CacheKeyManager.make_key("dispute", "stats", user_id=user.id)
        stats = cache.get(cache_key)
        if stats is not None:
            logger.info("Dispute stats (cached)")
            return stats

        start = timezone.now()

        agg = Dispute.objects.aggregate(
            total_disputes=Count("pk"),
            open_disputes=Count("pk", filter=Q(status=DisputeStatus.OPENED)),
            resolved_for_buyer=Count(
                "pk", filter=Q(status=DisputeStatus.RESOLVED_BUYER)
            ),
            resolved_for_seller=Count(
                "pk", filter=Q(status=DisputeStatus.RESOLVED_SELLER)
            ),
            closed_disputes=Count("pk", filter=Q(status=DisputeStatus.CLOSED)),
        )

        # Django’s aggregate returns a dict of ints
        cache.set(cache_key, agg, DisputeService.CACHE_TTL)

        elapsed_ms = (timezone.now() - start).total_seconds() * 1000
        logger.info(f"Computed dispute stats in {elapsed_ms:.2f}ms")

        return agg

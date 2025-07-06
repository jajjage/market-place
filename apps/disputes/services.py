from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Dispute, DisputeStatus


class DisputeService:
    """
    A service layer for handling dispute-related business logic.
    """

    @staticmethod
    @transaction.atomic
    def create_dispute(transaction_id, user, reason, description):
        """
        Create a new dispute for a transaction.
        """
        from apps.transactions.models import EscrowTransaction

        try:
            txn = EscrowTransaction.objects.get(id=transaction_id)
        except EscrowTransaction.DoesNotExist:
            raise ValidationError(_("Transaction not found"))

        if Dispute.objects.filter(transaction=txn).exists():
            raise ValidationError(_("A dispute already exists for this transaction"))

        if user not in [txn.buyer, txn.seller]:
            raise PermissionDenied(_("You cannot open a dispute for this transaction"))

        dispute = Dispute.objects.create(
            transaction=txn,
            opened_by=user,
            reason=reason,
            description=description,
            status=DisputeStatus.OPENED,
        )
        return dispute

    @staticmethod
    @transaction.atomic
    def resolve_dispute(dispute_id, resolver_user, status, resolution_note):
        """
        Resolve a dispute.
        """
        try:
            dispute = Dispute.objects.get(id=dispute_id)
        except Dispute.DoesNotExist:
            raise ValidationError(_("Dispute not found"))

        if not resolver_user.is_staff:
            raise PermissionDenied(_("Only staff can resolve disputes"))

        dispute.status = status
        dispute.resolution_note = resolution_note
        dispute.resolved_by = resolver_user
        dispute.save()
        return dispute

    @staticmethod
    def get_user_disputes(user, status_filter=None):
        """
        Get all disputes for a given user.
        """
        disputes = Dispute.objects.filter(
            Q(transaction__buyer=user) | Q(transaction__seller=user)
        )
        if status_filter:
            disputes = disputes.filter(status=status_filter)
        return disputes

    @staticmethod
    def get_stats(user):
        """
        Get dispute statistics.
        """
        if not user.is_staff:
            raise PermissionDenied(_("Only staff can view dispute statistics"))

        return Dispute.objects.aggregate(
            total_disputes=Count("id"),
            open_disputes=Count("id", filter=Q(status=DisputeStatus.OPENED)),
            resolved_disputes=Count(
                "id",
                filter=Q(status__in=[
                    DisputeStatus.RESOLVED_BUYER,
                    DisputeStatus.RESOLVED_SELLER,
                    DisputeStatus.CLOSED,
                ]),
            ),
        )
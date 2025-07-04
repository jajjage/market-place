from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.core.serializers import TimestampedModelSerializer
from .models import Dispute, DisputeReason, DisputeStatus

User = get_user_model()


class DisputeCreateSerializer(serializers.Serializer):
    """Serializer for creating disputes"""

    transaction_id = serializers.UUIDField(required=True)
    reason = serializers.ChoiceField(choices=DisputeReason.choices, required=True)
    description = serializers.CharField(required=True, max_length=5000)

    def validate_transaction_id(self, value):
        """Validate transaction exists and get the transaction object"""
        from apps.transactions.models import EscrowTransaction

        try:
            transaction = EscrowTransaction.objects.get(id=value)
        except EscrowTransaction.DoesNotExist:
            raise serializers.ValidationError(_("Transaction not found"))

        # Store transaction object for later use
        self.transaction = transaction
        return value

    def validate(self, attrs):
        """Validate that user can dispute this transaction"""
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        transaction = self.transaction

        # Check if dispute already exists
        if hasattr(transaction, "dispute"):
            raise serializers.ValidationError(
                _("A dispute already exists for this transaction")
            )

        # Only buyer or seller can open disputes
        if request.user not in [transaction.buyer, transaction.seller]:
            raise serializers.ValidationError(
                _("You can only dispute your own transactions")
            )

        # Check transaction status - disputes can only be opened for specific states
        DISPUTABLE_STATUSES = ["inspection", "completed", "funds_released"]
        if transaction.status not in DISPUTABLE_STATUSES:
            raise serializers.ValidationError(
                _(
                    "Disputes can only be opened for transactions in inspection, completed, or funds_released status. "
                    f"Current status: {transaction.get_status_display()}"
                )
            )
        # Store validated transaction object in attrs
        # attrs["transaction"] = transaction

        return attrs


class DisputeDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for dispute with related data"""

    opened_by_name = serializers.CharField(
        source="opened_by.get_full_name", read_only=True
    )
    resolved_by_name = serializers.CharField(
        source="resolved_by.get_full_name", read_only=True
    )
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    transaction_amount = serializers.DecimalField(
        source="transaction.amount", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Dispute
        fields = [
            "id",
            "transaction",
            "opened_by",
            "opened_by_name",
            "reason",
            "reason_display",
            "description",
            "status",
            "status_display",
            "resolved_by",
            "resolved_by_name",
            "resolution_note",
            "transaction_amount",
        ]
        read_only_fields = [
            "id",
            "opened_by",
            "resolved_by",
            "created_at",
            "updated_at",
        ]


class DisputeResolutionSerializer(TimestampedModelSerializer):
    """Serializer for resolving disputes (admin/staff only)"""

    class Meta:
        model = Dispute
        fields = ["status", "resolution_note"]

    def validate_status(self, value):
        """Validate status transition"""
        if value not in [
            DisputeStatus.RESOLVED_BUYER,
            DisputeStatus.RESOLVED_SELLER,
            DisputeStatus.CLOSED,
        ]:
            raise serializers.ValidationError(_("Invalid resolution status"))
        return value


class DisputeListSerializer(TimestampedModelSerializer):
    """Lightweight serializer for dispute lists"""

    opened_by_name = serializers.CharField(
        source="opened_by.get_full_name", read_only=True
    )
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Dispute
        fields = [
            "id",
            "transaction",
            "opened_by_name",
            "reason_display",
            "status_display",
            "created_at",
        ]

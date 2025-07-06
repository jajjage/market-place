from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.core.serializers import TimestampedModelSerializer
from apps.disputes.models import Dispute, DisputeReason, DisputeStatus
from apps.transactions.models import EscrowTransaction

User = get_user_model()


class DisputeCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a new dispute.

    This serializer validates the input data for creating a dispute, ensuring
    that the transaction exists and that the user is authorized to open a
    dispute for it.
    """

    transaction_id = serializers.UUIDField(required=True)
    reason = serializers.ChoiceField(choices=DisputeReason.choices, required=True)
    description = serializers.CharField(required=True, max_length=5000)

    def validate_transaction_id(self, value):
        """
        Validate that the transaction exists and store it for later use.
        """
        try:
            transaction = EscrowTransaction.objects.get(id=value)
        except EscrowTransaction.DoesNotExist:
            raise serializers.ValidationError(_("Transaction not found"))
        self.transaction = transaction
        return value

    def validate(self, attrs):
        """
        Validate that the user can dispute this transaction.

        This method checks if a dispute already exists for the transaction,
        if the user is the buyer or seller, and if the transaction is in a
        disputable state.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Authentication required"))

        transaction = self.transaction
        if hasattr(transaction, "dispute"):
            raise serializers.ValidationError(
                _("A dispute already exists for this transaction")
            )

        if request.user not in [transaction.buyer, transaction.seller]:
            raise serializers.ValidationError(
                _("You can only dispute your own transactions")
            )

        DISPUTABLE_STATUSES = ["inspection", "completed", "funds_released"]
        if transaction.status not in DISPUTABLE_STATUSES:
            raise serializers.ValidationError(
                _(
                    "Disputes can only be opened for transactions in inspection, "
                    f"completed, or funds_released status. Current status: {transaction.get_status_display()}"
                )
            )
        return attrs


class DisputeDetailSerializer(TimestampedModelSerializer):
    """
    Detailed serializer for the Dispute model.

    This serializer provides a comprehensive view of a dispute, including
    details about the users involved, the reason and status of the dispute,
    and information about the associated transaction.
    """

    opened_by_name = serializers.CharField(
        source="opened_by.get_full_name", read_only=True
    )
    resolved_by_name = serializers.CharField(
        source="resolved_by.get_full_name", read_only=True
    )
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    transaction_amount = serializers.DecimalField(
        source="transaction.amount",
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        read_only=True,
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "opened_by",
            "resolved_by",
            "created_at",
            "updated_at",
        ]


class DisputeResolutionSerializer(TimestampedModelSerializer):
    """
    Serializer for resolving a dispute.

    This serializer is used by staff members to update the status of a dispute
    and provide a resolution note.
    """

    class Meta:
        model = Dispute
        fields = ["status", "resolution_note"]

    def validate_status(self, value):
        """
        Validate that the new status is a valid resolution status.
        """
        if value not in [
            DisputeStatus.RESOLVED_BUYER,
            DisputeStatus.RESOLVED_SELLER,
            DisputeStatus.CLOSED,
        ]:
            raise serializers.ValidationError(_("Invalid resolution status"))
        return value


class DisputeListSerializer(TimestampedModelSerializer):
    """
    Lightweight serializer for listing disputes.

    This serializer provides a concise summary of a dispute, suitable for use
    in lists where a full representation is not required.
    """

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

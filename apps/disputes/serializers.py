from apps.core.serializers import TimestampedModelSerializer
from apps.disputes.models import Dispute
from rest_framework import serializers

from apps.transactions.serializers import EscrowTransactionShortSerializer


class DisputeSerializer(TimestampedModelSerializer):
    """Serializer for transaction disputes."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    opened_by_name = serializers.CharField(
        source="opened_by.get_full_name", read_only=True
    )
    transaction_details = EscrowTransactionShortSerializer(
        source="transaction", read_only=True
    )

    class Meta:
        model = Dispute
        fields = [
            "id",
            "transaction",
            "transaction_details",
            "opened_by",
            "opened_by_name",
            "reason",
            "reason_display",
            "description",
            "status",
            "status_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "opened_by", "status", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["opened_by"] = self.context["request"].user
        validated_data["status"] = "opened"
        return super().create(validated_data)

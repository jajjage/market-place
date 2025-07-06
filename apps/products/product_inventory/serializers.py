from rest_framework import serializers
from django.core.validators import MinValueValidator
from apps.core.serializers import TimestampedModelSerializer
from .models import InventoryTransaction


class InventoryActionSerializer(serializers.Serializer):
    """Base serializer for inventory actions"""

    quantity = serializers.IntegerField(
        max_value=1000,  # Use int for integer fields
        min_value=1,
        validators=[MinValueValidator(1)],
        help_text="Quantity must be a positive integer",
    )
    notes = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Optional notes for this inventory transaction",
    )
    variant_id = serializers.UUIDField(required=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be positive")
        return value


class AddInventorySerializer(InventoryActionSerializer):
    """Serializer for adding inventory to total"""

    pass


class ActivateInventorySerializer(InventoryActionSerializer):
    """Serializer for activating inventory (moving from total to available)"""

    quantity = serializers.IntegerField(
        max_value=1000,  # Use int for integer fields
        min_value=1,
        required=False,
        validators=[MinValueValidator(1)],
        help_text="Quantity to activate. If not provided, all inactive inventory will be activated",
    )


class UnifiedEscrowTransactionSerializer(serializers.Serializer):
    """
    Unified serializer for both direct and negotiation-based escrow transactions.
    """

    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    negotiation_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value


class ReleaseEscrowSerializer(InventoryActionSerializer):
    """Serializer for releasing inventory from escrow"""

    pass


class DeductInventorySerializer(InventoryActionSerializer):
    """Serializer for deducting inventory (completing sale)"""

    pass


class InventoryTransactionSerializer(TimestampedModelSerializer):
    """Serializer for inventory transaction details"""

    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    product_title = serializers.CharField(source="product.title", read_only=True)
    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )

    class Meta:
        model = InventoryTransaction
        fields = [
            "id",
            "transaction_type",
            "transaction_type_display",
            "quantity",
            "previous_total",
            "previous_available",
            "previous_in_escrow",
            "new_total",
            "new_available",
            "new_in_escrow",
            "notes",
            "created_at",
            "updated_at",
            "created_by_username",
            "product_title",
        ]
        read_only_fields = [
            "id",
            "transaction_type",
            "previous_total",
            "previous_available",
            "previous_in_escrow",
            "new_total",
            "new_available",
            "new_in_escrow",
            "created_at",
            "updated_at",
        ]


class InventoryStatusSerializer(serializers.Serializer):
    """Serializer for inventory status response"""

    status = serializers.CharField(read_only=True)
    total = serializers.IntegerField(
        max_value=1000, min_value=1, read_only=True  # Use int for integer fields
    )
    available = serializers.IntegerField(
        max_value=1000, min_value=1, read_only=True  # Use int for integer fields
    )
    in_escrow = serializers.IntegerField(
        max_value=1000, min_value=1, read_only=True  # Use int for integer fields
    )
    transaction_id = serializers.CharField(read_only=True, required=False)
    message = serializers.CharField(read_only=True, required=False)

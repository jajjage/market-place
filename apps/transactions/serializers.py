from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.products.serializers import ProductBaseSerializer
from .models.escrow_transactions import EscrowTransaction
from .models.transaction_dispute import Dispute
from .models.transaction_history import TransactionHistory

User = get_user_model()


class EscrowTransactionShortSerializer(serializers.ModelSerializer):
    """Basic transaction info for embedding in other serializers."""

    product_title = serializers.CharField(source="product.title")
    product_image = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display")

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "product_title",
            "product_image",
            "amount",
            "currency",
            "status",
            "status_display",
            "created_at",
        ]

    def get_product_image(self, obj):
        return (
            obj.product.images.first().image.url
            if obj.product.images.exists()
            else None
        )


class EscrowTransactionBaseSerializer(serializers.ModelSerializer):
    """Base serializer for EscrowTransaction with common fields."""

    # Import inside method to avoid circular import
    def get_user_serializer(self):
        from apps.users.serializers import PublicUserSerializer

        return PublicUserSerializer

    buyer = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    product = ProductBaseSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "product",
            "buyer",
            "seller",
            "amount",
            "currency",
            "status",
            "status_display",
            "inspection_period_days",
            "inspection_end_date",
            "tracking_number",
            "shipping_carrier",
            "shipping_address",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_buyer(self, obj):
        return self.get_user_serializer()(obj.buyer).data

    def get_seller(self, obj):
        return self.get_user_serializer()(obj.seller).data


class EscrowTransactionCreateSerializer(serializers.ModelSerializer):
    """Serializer for initiating a new escrow transaction."""

    class Meta:
        model = EscrowTransaction
        fields = [
            "product",
            "amount",
            "currency",
            "shipping_address",
            "notes",
            "inspection_period_days",
        ]

    def validate(self, data):
        """
        Validate the transaction creation:
        - Ensure product is available
        - Verify amount matches product price
        - Check if buyer != seller
        """
        product = data["product"]
        if not product.is_active:
            raise serializers.ValidationError("This product is no longer available")

        if product.inventory_count <= 0:
            raise serializers.ValidationError("This product is out of stock")

        if data["amount"] != product.price:
            raise serializers.ValidationError(
                "Transaction amount must match product price"
            )

        if self.context["request"].user == product.seller:
            raise serializers.ValidationError("You cannot buy your own product")

        return data

    def create(self, validated_data):
        # Set the buyer as the current user
        validated_data["buyer"] = self.context["request"].user
        # Set the seller from the product
        validated_data["seller"] = validated_data["product"].seller
        return super().create(validated_data)


class EscrowTransactionListSerializer(EscrowTransactionBaseSerializer):
    """Simplified serializer for listing transactions."""

    product = serializers.SerializerMethodField()

    class Meta(EscrowTransactionBaseSerializer.Meta):
        fields = [
            "id",
            "product",
            "amount",
            "currency",
            "status",
            "status_display",
            "created_at",
        ]

    def get_product(self, obj):
        return {
            "id": obj.product.id,
            "title": obj.product.title,
            "image": (
                obj.product.images.first().image.url
                if obj.product.images.exists()
                else None
            ),
        }


class EscrowTransactionDetailSerializer(EscrowTransactionBaseSerializer):
    """Detailed serializer with all transaction information."""

    can_update_status = serializers.SerializerMethodField()
    next_possible_statuses = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()

    class Meta(EscrowTransactionBaseSerializer.Meta):
        fields = EscrowTransactionBaseSerializer.Meta.fields + [
            "can_update_status",
            "next_possible_statuses",
            "time_remaining",
        ]

    def get_can_update_status(self, obj):
        user = self.context["request"].user
        current_status = obj.status

        # Define who can update to what status
        if user == obj.buyer:
            return current_status in ["initiated", "delivered"]
        elif user == obj.seller:
            return current_status in ["payment_received", "inspection"]
        return False

    def get_next_possible_statuses(self, obj):
        user = self.context["request"].user
        current_status = obj.status

        status_flow = {
            "initiated": ["payment_received"] if user == obj.buyer else [],
            "payment_received": ["shipped"] if user == obj.seller else [],
            "shipped": ["delivered"] if user == obj.buyer else [],
            "delivered": ["inspection"] if user == obj.seller else [],
            "inspection": ["completed", "disputed"] if user == obj.buyer else [],
            "completed": [],
            "disputed": [],
            "refunded": [],
            "cancelled": [],
        }

        return status_flow.get(current_status, [])

    def get_time_remaining(self, obj):
        if obj.status == "inspection" and obj.inspection_end_date:
            from django.utils import timezone

            remaining = obj.inspection_end_date - timezone.now()
            return max(0, int(remaining.total_seconds()))
        return None


class EscrowTransactionStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating transaction status."""

    class Meta:
        model = EscrowTransaction
        fields = ["status", "notes", "tracking_number", "shipping_carrier"]

    def validate_status(self, value):
        current_status = self.instance.status
        user = self.context["request"].user

        # Define valid status transitions
        valid_transitions = {
            "initiated": {"buyer": ["payment_received"], "seller": []},
            "payment_received": {"buyer": [], "seller": ["shipped"]},
            "shipped": {"buyer": ["delivered"], "seller": []},
            "delivered": {"buyer": [], "seller": ["inspection"]},
            "inspection": {"buyer": ["completed", "disputed"], "seller": []},
        }

        # Get valid next statuses for current user
        user_role = "buyer" if user == self.instance.buyer else "seller"
        valid_next_statuses = valid_transitions.get(current_status, {}).get(
            user_role, []
        )

        if value not in valid_next_statuses:
            raise serializers.ValidationError(
                f"Invalid status transition from {current_status} to {value} for {user_role}"
            )

        return value


class TransactionHistorySerializer(serializers.ModelSerializer):
    """Serializer for transaction history entries."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = TransactionHistory
        fields = [
            "id",
            "transaction",
            "status",
            "status_display",
            "timestamp",
            "notes",
            "created_by",
            "created_by_name",
        ]
        read_only_fields = ["id", "timestamp", "created_by"]


class DisputeSerializer(serializers.ModelSerializer):
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

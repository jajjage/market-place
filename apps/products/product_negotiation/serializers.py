from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal

from apps.core.serializers import (
    ProductSummarySerializer,
    TimestampedModelSerializer,
    UserShortSerializer,
    VariantShortSerializer,
)
from apps.products.product_negotiation.models import (
    PriceNegotiation,
    NegotiationHistory,
)


class NegotiationHistorySerializer(TimestampedModelSerializer):
    """Serializer for negotiation history"""

    user = UserShortSerializer(read_only=True)
    formatted_price = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = NegotiationHistory
        fields = [
            "id",
            "action",
            "user",
            "price",
            "formatted_price",
            "timestamp",
            "time_ago",
            "notes",
        ]

    def get_formatted_price(self, obj) -> str | None:
        if obj.price:
            return f"${obj.price:,.2f}"
        return None

    def get_time_ago(self, obj) -> str | None:
        """Human readable time difference"""
        now = timezone.now()
        diff = now - obj.timestamp

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"


class PriceNegotiationSerializer(TimestampedModelSerializer):
    """Main serializer for price negotiations"""

    product = ProductSummarySerializer(read_only=True)
    buyer = UserShortSerializer(read_only=True)
    seller = UserShortSerializer(read_only=True)
    variant = VariantShortSerializer(read_only=True)
    history = NegotiationHistorySerializer(many=True, read_only=True)

    # Formatted price fields
    formatted_original_price = serializers.SerializerMethodField()
    formatted_offered_price = serializers.SerializerMethodField()
    formatted_final_price = serializers.SerializerMethodField()

    # Calculated fields
    discount_amount = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    can_respond = serializers.SerializerMethodField()

    # Status display
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PriceNegotiation
        fields = [
            "id",
            "product",
            "buyer",
            "seller",
            "variant",
            "formatted_original_price",
            "formatted_offered_price",
            "formatted_final_price",
            "status_display",
            "discount_amount",
            "discount_percentage",
            "offered_at",
            "time_remaining",
            "can_respond",
            "history",
        ]

    def get_formatted_original_price(self, obj) -> str:
        return f"${obj.original_price:,.2f}"

    def get_formatted_offered_price(self, obj) -> str:
        return f"${obj.offered_price:,.2f}"

    def get_formatted_final_price(self, obj) -> str | None:
        if obj.final_price:
            return f"${obj.final_price:,.2f}"
        return None

    def get_discount_amount(self, obj) -> float:
        """Calculate discount amount from original price"""
        price_to_compare = obj.final_price or obj.offered_price
        return float(obj.original_price - price_to_compare)

    def get_discount_percentage(self, obj) -> float:
        """Calculate discount percentage"""
        price_to_compare = obj.final_price or obj.offered_price
        if obj.original_price > 0:
            return round(
                ((obj.original_price - price_to_compare) / obj.original_price) * 100, 2
            )
        return 0

    def get_time_remaining(self, obj) -> str | None:
        """Calculate time remaining for negotiation response"""
        if obj.product.negotiation_deadline:
            now = timezone.now()
            if now < obj.product.negotiation_deadline:
                diff = obj.product.negotiation_deadline - now
                if diff.days > 0:
                    return f"{diff.days} days remaining"
                elif diff.seconds > 3600:
                    hours = diff.seconds // 3600
                    return f"{hours} hours remaining"
                else:
                    minutes = diff.seconds // 60
                    return f"{minutes} minutes remaining"
            else:
                return "Expired"
        return None

    def get_can_respond(self, obj) -> bool:
        """Check if current user can respond to this negotiation"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        user = request.user

        # Seller can respond if status is pending or countered
        if user == obj.seller and obj.status in ["pending", "countered"]:
            return True

        # Buyer can respond if status is countered
        if user == obj.buyer and obj.status == "countered":
            return True

        return False


class InitiateNegotiationSerializer(serializers.Serializer):
    """Serializer for initiating a negotiation"""

    offered_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    variant_id = serializers.UUIDField(required=True)

    def validate_offered_price(self, value):
        """Validate offered price"""
        if value <= 0:
            raise serializers.ValidationError("Offered price must be greater than zero")
        return value


class NegotiationResponseSerializer(serializers.Serializer):
    """Unified serializer for all negotiation responses"""

    RESPONSE_CHOICES = [
        ("accept", "Accept"),
        ("reject", "Reject"),
        ("counter", "Counter"),
    ]

    response_type = serializers.ChoiceField(choices=RESPONSE_CHOICES)
    counter_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, data):
        """Cross-field validation"""
        if data.get("response_type") == "counter":
            if not data.get("counter_price"):
                raise serializers.ValidationError(
                    {
                        "counter_price": "Counter price is required when making a counter offer"
                    }
                )
            if data.get("counter_price") <= 0:
                raise serializers.ValidationError(
                    {"counter_price": "Counter price must be greater than zero"}
                )
        return data


class CreateTransactionFromNegotiationSerializer(serializers.Serializer):
    """Serializer for creating transaction from accepted negotiation"""

    quantity = serializers.IntegerField(
        max_value=1000, min_value=1, default=1  # Use int for integer fields
    )
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    shipping_address = serializers.JSONField(required=False)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value


class NegotiationStatsSerializer(serializers.Serializer):
    """Serializer for negotiation statistics"""

    total_negotiations = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    accepted_negotiations = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    rejected_negotiations = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    pending_negotiations = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    average_offered_price = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )
    average_final_price = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )
    success_rate = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )

    # Additional calculated fields
    formatted_avg_offered_price = serializers.SerializerMethodField()
    formatted_avg_final_price = serializers.SerializerMethodField()
    success_rate_display = serializers.SerializerMethodField()

    def get_formatted_avg_offered_price(self, obj) -> str:
        return (
            f"${obj['average_offered_price']:,.2f}"
            if obj["average_offered_price"]
            else "$0.00"
        )

    def get_formatted_avg_final_price(self, obj) -> str:
        return (
            f"${obj['average_final_price']:,.2f}"
            if obj["average_final_price"]
            else "$0.00"
        )

    def get_success_rate_display(self, obj) -> str:
        return f"{obj['success_rate']:.1f}%" if obj["success_rate"] else "0.0%"


class UserNegotiationHistorySerializer(serializers.Serializer):
    """Serializer for user's negotiation history"""

    id = serializers.UUIDField()
    product_name = serializers.CharField()
    original_price = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )
    offered_price = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )
    final_price = serializers.FloatField(
        max_value=5.0, min_value=0.0, allow_null=True  # Use float for float fields
    )
    status = serializers.CharField()
    role = serializers.CharField()  # 'buyer' or 'seller'
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    # Formatted fields
    formatted_original_price = serializers.SerializerMethodField()
    formatted_offered_price = serializers.SerializerMethodField()
    formatted_final_price = serializers.SerializerMethodField()
    outcome = serializers.SerializerMethodField()

    def get_formatted_original_price(self, obj) -> str:
        return f"${obj['original_price']:,.2f}"

    def get_formatted_offered_price(self, obj) -> str:
        return f"${obj['offered_price']:,.2f}"

    def get_formatted_final_price(self, obj) -> str | None:
        if obj["final_price"]:
            return f"${obj['final_price']:,.2f}"
        return None

    def get_outcome(self, obj) -> str:
        """Get negotiation outcome description"""
        if obj["status"] == "accepted":
            final_price = obj["final_price"] or obj["offered_price"]
            savings = obj["original_price"] - final_price
            if savings > 0:
                return f"Saved ${savings:,.2f}"
            else:
                return "Accepted at offered price"
        elif obj["status"] == "rejected":
            return "Offer rejected"
        elif obj["status"] in ["pending", "countered"]:
            return "Negotiation ongoing"
        return obj["status"].title()

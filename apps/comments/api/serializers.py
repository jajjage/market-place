from decimal import Decimal
from rest_framework import serializers
from apps.core.serializers import TimestampedModelSerializer, UserShortSerializer
from apps.transactions.models.transaction import EscrowTransaction
from ..models import UserRating


class RatingCreateSerializer(serializers.Serializer):
    """Simplified serializer for creating ratings - business logic handled in service"""

    rating = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    transaction_id = serializers.CharField(
        max_length=1000, required=False, allow_blank=True
    )

    def validate_rating(self, value):
        if value not in range(1, 6):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def validate(self, data):
        # 1. Fetch the transaction
        try:
            tx = EscrowTransaction.objects.get(pk=data["transaction_id"])
        except EscrowTransaction.DoesNotExist:
            raise serializers.ValidationError(
                {"transaction_id": "Invalid transaction ID."}
            )

        # 2. Define allowed statuses using the model constants
        allowed = {
            EscrowTransaction.STATUS_COMPLETED,
            EscrowTransaction.STATUS_FUNDS_RELEASED,
        }

        # 3. Check the raw .status field
        if tx.status not in allowed:
            raise serializers.ValidationError(
                {
                    "non_field_errors": "You can only rate transactions that are Completed or Funds Released."
                }
            )

        # 4. (Optional) Prevent double‑rating
        if hasattr(tx, "ratings") and tx.ratings.exists():
            raise serializers.ValidationError(
                {"non_field_errors": "This transaction has already been rated."}
            )

        # Attach the transaction instance for use in .create()
        self.transaction = tx
        return data


class RatingDetailSerializer(TimestampedModelSerializer):
    from_user = UserShortSerializer(read_only=True)
    to_user = UserShortSerializer(read_only=True)
    transaction_title = serializers.CharField(
        source="transaction.title", read_only=True
    )
    transaction_date = serializers.DateTimeField(
        source="transaction.status_changed_at", read_only=True
    )

    class Meta:
        model = UserRating
        fields = [
            "id",
            "rating",
            "comment",
            "created_at",
            "updated_at",
            "is_verified",
            "from_user",
            "to_user",
            "transaction_title",
            "transaction_date",
        ]


class RatingListSerializer(TimestampedModelSerializer):
    from_user_name = serializers.CharField(
        source="from_user.get_full_name", read_only=True
    )
    transaction_title = serializers.CharField(
        source="transaction.title", read_only=True
    )

    class Meta:
        model = UserRating
        fields = [
            "id",
            "rating",
            "comment",
            "created_at",
            "is_verified",
            "from_user_name",
            "transaction_title",
        ]


class RatingEligibilitySerializer(serializers.Serializer):
    """Legacy serializer for transaction-based eligibility"""

    can_rate = serializers.BooleanField()
    reason = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)
    transaction_id = serializers.UUIDField()
    seller_name = serializers.CharField(allow_null=True)


class RateableTransactionSerializer(serializers.Serializer):
    """Serializer for individual rateable transactions"""

    transaction_id = serializers.UUIDField()
    transaction_title = serializers.CharField()
    transaction_amount = serializers.CharField()
    status_changed_at = serializers.DateTimeField()
    rating_deadline = serializers.DateTimeField()
    days_remaining = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )


class BuyerSellerEligibilitySerializer(serializers.Serializer):
    """Robust serializer for buyer-seller rating eligibility"""

    can_rate = serializers.BooleanField()
    reason = serializers.CharField()
    rateable_transactions = RateableTransactionSerializer(many=True)
    total_completed_transactions = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    seller_name = serializers.CharField(allow_null=True)
    seller_id = serializers.UUIDField()


class RatingStatsSerializer(serializers.Serializer):
    average_rating = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )
    total_ratings = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    rating_distribution = serializers.DictField()
    recent_ratings_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )


class PendingRatingSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    transaction_title = serializers.CharField()
    seller_name = serializers.CharField()
    status_changed_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    days_remaining = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )

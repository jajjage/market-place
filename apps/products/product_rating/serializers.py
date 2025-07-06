from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.core.serializers import TimestampedModelSerializer, UserShortSerializer

from .models import (
    ProductRating,
    ProductRatingAggregate,
    RatingHelpfulness,
)

User = get_user_model()


class ProductRatingsListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRating
        fields = [
            "id",
            "rating",
            "review",
            "title",
        ]
        read_only_fields = ["id", "rating", "review", "title"]


class ProductRatingsSerializer(TimestampedModelSerializer):
    user = UserShortSerializer(read_only=True)
    helpfulness_ratio = serializers.ReadOnlyField()
    can_vote = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    product_title = serializers.CharField(source="product.title", read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = ProductRating
        fields = [
            "id",
            "rating",
            "review",
            "title",
            "is_verified_purchase",
            "helpful_count",
            "total_votes",
            "helpfulness_ratio",
            "user",
            "can_vote",
            "user_vote",
            "product_title",
            "is_owner",
        ]

    def get_can_vote(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user != obj.user

    def get_user_vote(self, obj) -> bool | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        try:
            vote = RatingHelpfulness.objects.get(rating=obj, user=request.user)
            return vote.is_helpful
        except RatingHelpfulness.DoesNotExist:
            return None

    def get_is_owner(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user == obj.user


class RatingBreakdownSerializer(serializers.Serializer):
    stars = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    percentage = serializers.SerializerMethodField()

    def get_percentage(self, obj) -> float:
        total = self.context.get("total_count", 0)
        if total == 0:
            return 0
        return round((obj["count"] / total) * 100, 1)


class ProductRatingAggregateSerializer(TimestampedModelSerializer):
    average = serializers.DecimalField(
        source="average_rating",
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )
    count = serializers.IntegerField(
        max_value=1000, min_value=1, source="total_count"  # Use int for integer fields
    )
    verified_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    breakdown = serializers.SerializerMethodField()

    class Meta:
        model = ProductRatingAggregate
        fields = [
            "average",
            "count",
            "verified_count",
            "breakdown",
            "has_reviews",
            "last_rating_date",
        ]

    def get_breakdown(self, obj) -> list[dict]:
        breakdown_data = obj.rating_breakdown
        serializer = RatingBreakdownSerializer(
            breakdown_data, many=True, context={"total_count": obj.total_count}
        )
        return serializer.data


class CreateRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductRating
        fields = ["rating", "review", "title"]

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

    def validate_review(self, value):
        """Make review mandatory and ensure minimum length"""
        if not value or not value.strip():
            raise serializers.ValidationError("Review text is required for all ratings")

        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Review must be at least 10 characters long"
            )

        if len(value.strip()) > 2000:
            raise serializers.ValidationError("Review cannot exceed 2000 characters")

        return value.strip()

    def validate_title(self, value):
        """Optional title with length validation"""
        if value and len(value.strip()) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters")
        return value.strip() if value else ""


class RatingFilterSerializer(serializers.Serializer):
    """Serializer for rating filter parameters"""

    product_id = serializers.UUIDField(required=True)
    page = serializers.IntegerField(
        default=1, max_value=1000, min_value=1  # Use int for integer fields
    )
    per_page = serializers.IntegerField(
        default=10,
        min_value=1,
        max_value=50,
    )
    rating = serializers.IntegerField(required=False, max_value=5, min_value=1)
    sort = serializers.ChoiceField(
        choices=["newest", "oldest", "helpful", "rating_high", "rating_low"],
        default="newest",
    )
    verified_only = serializers.BooleanField(default=False)


class UserRatingStatsSerializer(serializers.Serializer):
    """Serializer for user rating statistics"""

    total_ratings = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    average_rating_given = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )
    verified_purchases_rated = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    helpful_votes_received = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )

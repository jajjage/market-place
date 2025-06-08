from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.core.serializers import TimestampedModelSerializer, UserShortSerializer

from .models import (
    ProductRating,
    ProductRatingAggregate,
    RatingHelpfulness,
)

User = get_user_model()


class ProductRatingsSummarySerializer(serializers.Serializer):
    """
    Serializer for product ratings summary.
    This works with Product instances, not ProductRating instances.
    """

    average_rating = serializers.SerializerMethodField()
    total_ratings = serializers.SerializerMethodField()
    # rating_breakdown = serializers.SerializerMethodField()

    def get_average_rating(self, obj):
        """Get average rating - uses annotated field if available, otherwise calculates"""
        # Use annotated field if available (more efficient)
        if hasattr(obj, "average_rating") and obj.average_rating is not None:
            return round(float(obj.average_rating), 2)

        # Fallback to calculation using prefetched ratings
        ratings = obj.ratings.all()
        if ratings:
            return round(sum(r.rating for r in ratings) / len(ratings), 2)
        return 0.0

    def get_total_ratings(self, obj):
        """Get total number of ratings - uses annotated field if available"""
        # Use annotated field if available (more efficient)
        if hasattr(obj, "total_ratings"):
            return obj.total_ratings

        # Fallback to count using prefetched ratings
        return obj.ratings.count()

    # def get_rating_breakdown(self, obj):
    #     """Get breakdown of ratings by star count (1-5)"""
    #     from collections import Counter

    #     # Use prefetched ratings to avoid additional queries
    #     ratings = [r.rating for r in obj.ratings.all()]
    #     breakdown = Counter(ratings)

    #     # Return breakdown for stars 1-5
    #     return {f"{i}_star": breakdown.get(i, 0) for i in range(1, 6)}


class ProductRatingsSerializer(TimestampedModelSerializer):
    user = UserShortSerializer(read_only=True)
    helpfulness_ratio = serializers.ReadOnlyField()
    can_vote = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = ProductRating
        fields = [
            "id",
            "rating",
            "review",
            "title",
            "created_at",
            "is_verified_purchase",
            "helpful_count",
            "total_votes",
            "helpfulness_ratio",
            "user",
            "can_vote",
            "user_vote",
        ]

    def get_can_vote(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user != obj.user

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        try:
            vote = RatingHelpfulness.objects.get(rating=obj, user=request.user)
            return vote.is_helpful
        except RatingHelpfulness.DoesNotExist:
            return None


class RatingBreakdownSerializer(serializers.Serializer):
    stars = serializers.IntegerField()
    count = serializers.IntegerField()
    percentage = serializers.SerializerMethodField()

    def get_percentage(self, obj):
        total = self.context.get("total_count", 0)
        if total == 0:
            return 0
        return round((obj["count"] / total) * 100, 1)


class ProductRatingAggregateSerializer(TimestampedModelSerializer):
    average = serializers.DecimalField(
        source="average_rating", max_digits=3, decimal_places=2
    )
    count = serializers.IntegerField(source="total_count")
    verified_count = serializers.IntegerField()
    breakdown = serializers.SerializerMethodField()

    class Meta:
        model = ProductRatingAggregate
        fields = ["average", "count", "verified_count", "breakdown", "has_reviews"]

    def get_breakdown(self, obj):
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

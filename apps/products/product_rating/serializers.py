from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import (
    ProductRating,
    ProductRatingAggregate,
    RatingHelpfulness,
)

User = get_user_model()


class RatingUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name"]


class ProductRatingsSerializer(serializers.ModelSerializer):
    user = RatingUserSerializer(read_only=True)
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


class ProductRatingAggregateSerializer(serializers.ModelSerializer):
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

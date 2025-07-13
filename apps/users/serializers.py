from rest_framework import serializers
from django.db.models import Sum
from apps.comments.api.serializers import RatingListSerializer
from apps.core.serializers import TimestampedModelSerializer, get_timestamp_fields
from apps.disputes.api.serializers import DisputeListSerializer
from apps.users.models import UserProfile
from apps.users.models.user_address import UserAddress
from apps.transactions.api.serializers import (
    TransactionHistorySerializer,
)
from apps.users.utils.total_sales import get_seller_sales_summary


class SellerReviewsSerializer(serializers.Serializer):
    positive = serializers.SerializerMethodField()
    neutral = serializers.SerializerMethodField()
    negative = serializers.SerializerMethodField()

    def get_positive(self, obj) -> int:
        return obj.reviews.filter(review_type="positive").count()

    def get_neutral(self, obj) -> int:
        return obj.reviews.filter(review_type="neutral").count()

    def get_negative(self, obj) -> int:
        return obj.reviews.filter(review_type="negative").count()


class UserAddressSerializer(TimestampedModelSerializer):
    class Meta:
        model = UserAddress
        fields = [
            "id",
            "address_type",
            "is_default",
            "name",
            "street_address",
            "apartment",
            "city",
            "state",
            "postal_code",
            "country",
            "phone",
        ] + get_timestamp_fields(UserAddress)
        read_only_fields = ["id"] + get_timestamp_fields(UserAddress)


class UserProfileSerializer(TimestampedModelSerializer):
    # reviews = SellerReviewsSerializer(source="*", read_only=True)
    addresses = UserAddressSerializer(many=True, required=False)
    received_ratings = RatingListSerializer(
        many=True, read_only=True
    )  # Always read-only for security

    disputes = DisputeListSerializer(
        many=True, read_only=True, source="opened_disputes"
    )
    transaction_history = TransactionHistorySerializer(
        many=True, read_only=True, source="created_transaction_history"
    )
    memberSince = serializers.SerializerMethodField()
    transactions_completed = serializers.SerializerMethodField(read_only=True)
    total_sales = serializers.SerializerMethodField(read_only=True)
    total_purchases = serializers.SerializerMethodField(read_only=True)
    verified_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "display_name",
            "bio",
            "email_verified",
            "phone_verified",
            "identity_verified",
            "phone_number",
            "country",
            "city",
            "location",
            "avatar_url",
            "disputes",
            "transaction_history",
            "addresses",
            "response_rate",
            "response_time",
            "received_ratings",
            "positive_percentage",
            "memberSince",
            "location",
            "response_rate",
            "response_time",
            # "reviews",
            "is_verified",
            "last_active",
            "transactions_completed",
            "notification_email",
            "notification_sms",
            "average_rating",
            "verified_status",
            "total_sales",
            "total_purchases",
        ] + get_timestamp_fields(UserProfile)
        read_only_fields = [
            "id",
            "average_rating",
            "verified_status",
            "total_sales",
            "total_purchases",
            "member_since",
            "last_active",
        ] + get_timestamp_fields(UserProfile)

    def get_transactions_completed(self, obj) -> int:
        """Get total completed transactions (as buyer + seller)"""
        # Try to get from annotations first (if available)
        if hasattr(obj, "completed_as_seller") and hasattr(obj, "completed_as_buyer"):
            return obj.completed_as_seller + obj.completed_as_buyer

        # # Fallback to database queries
        seller_completed = obj.user.seller_transactions.filter(
            status="completed"
        ).count()
        buyer_completed = obj.user.buyer_transactions.filter(status="completed").count()
        return seller_completed + buyer_completed

    def get_total_sales(self, obj) -> int:
        """Get total sales amount from completed transactions"""
        # Try to get from annotations first
        sales_data = get_seller_sales_summary(obj.user)

        # Format the output
        if not sales_data:
            # Fallback to database query
            return (
                obj.user.seller_transactions.filter(status="completed").aggregate(
                    total=Sum("total_amount")
                )["total"]
                or 0
            )
        return {
            "withdrawable_funds": f"{sales_data['withdrawable_funds'] or 0:,.2f}",
            "current_month_active_sales": f"{sales_data['current_month_active_sales'] or 0:,.2f}",
            "all_time_active_sales": f"{sales_data['all_time_active_sales'] or 0:,.2f}",
            "percentage_change": sales_data["percentage_change"],
            "is_increase": sales_data["is_increase"],
        }

    def get_total_purchases(self, obj) -> int:
        """Get total purchase amount from completed transactions"""
        # Try to get from annotations first
        if hasattr(obj, "completed_as_buyer"):
            return obj.completed_as_buyer or 0

        # Fallback to database query
        return (
            obj.user.buyer_transactions.filter(status="completed").aggregate(
                total=Sum("total_amount")
            )["total"]
            or 0
        )

    def get_memberSince(self, obj) -> str:
        return obj.member_since.strftime("%b %Y")

    def get_verified_status(self, obj) -> bool:
        return getattr(obj, "verified_status", False)


class PublicUserProfileSerializer(serializers.ModelSerializer):
    # keep the computed fields you’re happy sharing
    # reviews = SellerReviewsSerializer(source="*", read_only=True)
    memberSince = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    verified_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "display_name",
            "full_name",
            "avatar_url",
            "is_verified",
            "bio",
            # "reviews",
            "verified_status",
            "country",
            "city",
            "positive_percentage",
            "location",
            "response_rate",
            "response_time",
            "memberSince",
            "average_rating",
        ]
        read_only_fields = fields

    def get_full_name(self, obj) -> str:
        return obj.user.get_full_name()

    def get_memberSince(self, obj) -> str:
        return obj.member_since.strftime("%b %Y")

    def get_verified_status(self, obj) -> bool:
        return getattr(obj, "verified_status", False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if hasattr(instance, "userprofile") and instance.userprofile.avatar_url:
                data["avatar_url"] = instance.userprofile.avatar_url
            else:
                data["avatar_url"] = None
        except (ValueError, AttributeError):
            data["avatar_url"] = None

        return data

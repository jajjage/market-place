# users/api/serializers.py

from rest_framework import serializers
from django.db.models import Sum
from apps.comments.serializers import RatingListSerializer
from apps.core.serializers import TimestampedModelSerializer, get_timestamp_fields
from apps.disputes.serializers import DisputeListSerializer
from apps.store.serializers import UserStoreSerializer
from apps.users.models import CustomUser, UserProfile
from apps.users.models.user_address import UserAddress
from apps.transactions.serializers import (
    TransactionHistorySerializer,
)


class SellerReviewsSerializer(serializers.Serializer):
    positive = serializers.SerializerMethodField()
    neutral = serializers.SerializerMethodField()
    negative = serializers.SerializerMethodField()

    def get_positive(self, obj):
        return obj.reviews.filter(review_type="positive").count()

    def get_neutral(self, obj):
        return obj.reviews.filter(review_type="neutral").count()

    def get_negative(self, obj):
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
    reviews = SellerReviewsSerializer(source="*", read_only=True)
    memberSince = serializers.SerializerMethodField()
    transactions_completed = serializers.SerializerMethodField(read_only=True)
    total_sales = serializers.SerializerMethodField(read_only=True)
    total_purchases = serializers.SerializerMethodField(read_only=True)

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
            "positive_percentage",
            "memberSince",
            "location",
            "response_rate",
            "response_time",
            "reviews",
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

    def get_transactions_completed(self, obj):
        """Get total completed transactions (as buyer + seller)"""
        # Try to get from annotations first (if available)
        if hasattr(obj.user, "completed_sales_count") and hasattr(
            obj.user, "completed_purchases_count"
        ):
            return obj.user.completed_sales_count + obj.user.completed_purchases_count

        # Fallback to database queries
        seller_completed = obj.user.seller_transactions.filter(
            status="completed"
        ).count()
        buyer_completed = obj.user.buyer_transactions.filter(status="completed").count()
        return seller_completed + buyer_completed

    def get_total_sales(self, obj):
        """Get total sales amount from completed transactions"""
        # Try to get from annotations first
        if hasattr(obj.user, "total_sales_amount"):
            return obj.user.total_sales_amount or 0

        # Fallback to database query
        return (
            obj.user.seller_transactions.filter(status="completed").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

    def get_total_purchases(self, obj):
        """Get total purchase amount from completed transactions"""
        # Try to get from annotations first
        if hasattr(obj.user, "total_purchases_amount"):
            return obj.user.total_purchases_amount or 0

        # Fallback to database query
        return (
            obj.user.buyer_transactions.filter(status="completed").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

    def get_memberSince(self, obj):
        return obj.member_since.strftime("%b %Y")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Rename fields to match desired format
        data["isVerified"] = data.pop("is_verified")
        data["totalSales"] = data.pop("total_sales")
        data["positivePercentage"] = data.pop("positive_percentage")
        data["responseRate"] = data.pop("response_rate")
        data["responseTime"] = data.pop("response_time")
        return data


class UserSerializer(TimestampedModelSerializer):
    profile = UserProfileSerializer(required=False)
    store = UserStoreSerializer(required=False)
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

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "profile",
            "store",
            "addresses",
            "received_ratings",
            "disputes",
            "transaction_history",
        ] + get_timestamp_fields(CustomUser)
        read_only_fields = ["id", "verification_status"] + get_timestamp_fields(
            CustomUser
        )

    def update(self, instance, validated_data):
        # Handle nested updates only if user is owner

        profile_data = validated_data.pop("profile", None)
        store_data = validated_data.pop("store", None)
        addresses_data = validated_data.pop("addresses", None)

        # Update main user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update profile
        if profile_data and hasattr(instance, "profile"):
            profile_serializer = UserProfileSerializer(
                instance.profile, data=profile_data, partial=True
            )
            if profile_serializer.is_valid(raise_exception=True):
                profile_serializer.save()

        # Update store
        if store_data and hasattr(instance, "store"):
            store_serializer = UserStoreSerializer(
                instance.store, data=store_data, partial=True
            )
            if store_serializer.is_valid(raise_exception=True):
                store_serializer.save()

        # Update addresses
        if addresses_data is not None:  # Allow empty list to clear addresses
            # Clear existing addresses and create new ones
            instance.addresses.all().delete()
            for address_data in addresses_data:
                UserAddress.objects.create(user=instance, **address_data)

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if hasattr(instance, "profile") and instance.profile.avatar_url:
                data["avatar_url"] = instance.profile.avatar_url
            else:
                data["avatar_url"] = None
        except (ValueError, AttributeError):
            data["avatar_url"] = None
        return data


class PublicUserProfileSerializer(serializers.ModelSerializer):
    # keep the computed fields you’re happy sharing
    reviews = SellerReviewsSerializer(source="*", read_only=True)
    memberSince = serializers.SerializerMethodField()
    transactions_completed = serializers.SerializerMethodField(read_only=True)
    total_sales = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "display_name",
            "full_name",
            "avatar_url",
            "is_verified",
            "bio",
            "reviews",
            "transactions_completed",
            "country",
            "city",
            "positive_percentage",
            "location",
            "response_rate",
            "response_time",
            "memberSince",
            "average_rating",
            "total_sales",
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.user.get_full_name()

    def get_transactions_completed(self, obj):
        """Get total completed transactions (as buyer + seller)"""
        # Try to get from annotations first (if available)
        if hasattr(obj.user, "completed_sales_count") and hasattr(
            obj.user, "completed_purchases_count"
        ):
            return obj.user.completed_sales_count + obj.user.completed_purchases_count

        # Fallback to database queries
        seller_completed = obj.user.seller_transactions.filter(
            status="completed"
        ).count()
        buyer_completed = obj.user.buyer_transactions.filter(status="completed").count()
        return seller_completed + buyer_completed

    def get_total_sales(self, obj):
        """Get total sales amount from completed transactions"""
        # Try to get from annotations first
        if hasattr(obj.user, "total_sales_amount"):
            return obj.user.total_sales_amount or 0

        # Fallback to database query
        return (
            obj.user.seller_transactions.filter(status="completed").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

    def get_memberSince(self, obj):
        return obj.member_since.strftime("%b %Y")

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


class PublicUserSerializer(serializers.ModelSerializer):
    """Only the fields you’re okay exposing to others."""

    full_name = serializers.SerializerMethodField()
    profile = PublicUserProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "full_name", "profile"]
        # no email, no addresses, no private store, no ratings…

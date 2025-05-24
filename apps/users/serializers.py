# users/api/serializers.py
from rest_framework import serializers
from apps.comments.serializers import UserRatingSerializer
from apps.core.serializers import TimestampedModelSerializer, get_timestamp_fields
from apps.disputes.serializers import DisputeSerializer
from apps.store.serializers import UserStoreSerializer
from apps.users.models import CustomUser, UserProfile
from apps.users.models.user_address import UserAddress
from apps.transactions.serializers import (
    EscrowTransactionShortSerializer,
    TransactionHistorySerializer,
)


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
    average_rating = serializers.FloatField(read_only=True)
    verified_status = serializers.CharField(read_only=True)
    total_sales = serializers.IntegerField(read_only=True)
    total_purchases = serializers.IntegerField(read_only=True)

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
            "member_since",
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


class UserSerializer(TimestampedModelSerializer):
    profile = UserProfileSerializer(required=False)
    store = UserStoreSerializer(required=False)
    addresses = UserAddressSerializer(many=True, required=False)
    received_ratings = UserRatingSerializer(
        many=True, read_only=True
    )  # Always read-only for security
    purchases = serializers.SerializerMethodField()
    sales = serializers.SerializerMethodField()
    disputes = DisputeSerializer(many=True, read_only=True, source="opened_disputes")
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
            "verification_status",
            "profile",
            "store",
            "addresses",
            "received_ratings",
            "purchases",
            "sales",
            "disputes",
            "transaction_history",
        ] + get_timestamp_fields(CustomUser)
        read_only_fields = ["id", "verification_status"] + get_timestamp_fields(
            CustomUser
        )

    def get_purchases(self, obj):
        """Get user's purchases using the short serializer"""
        purchases = obj.buyer_transactions.all()
        return EscrowTransactionShortSerializer(purchases, many=True).data

    def get_sales(self, obj):
        """Get user's sales using the short serializer"""
        sales = obj.seller_transactions.all()
        return EscrowTransactionShortSerializer(sales, many=True).data

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
    average_rating = serializers.FloatField(read_only=True)
    total_sales = serializers.IntegerField(read_only=True)
    total_purchases = serializers.IntegerField(read_only=True)
    verification_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "display_name",
            "avatar_url",
            "verification_status",
            "bio",
            "country",
            "city",
            "member_since",
            "average_rating",
            "total_sales",
            "total_purchases",
        ]
        read_only_fields = fields

    def get_verification_status(self, obj):
        status = obj.user.verification_status
        return status

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

    profile = PublicUserProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "profile"]
        # no email, no addresses, no private store, no ratings…

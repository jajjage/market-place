# users/api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.users.models import CustomUser, UserProfile
from apps.users.models.user_store import UserStore
from apps.users.models.user_rating import UserRating
from apps.users.models.user_address import UserAddress
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


# Base serializer for DRY timestamp fields
def get_timestamp_fields(model):
    fields = []
    for f in ["created_at", "updated_at"]:
        if hasattr(model, f):
            fields.append(f)
    return fields


class TimestampedModelSerializer(serializers.ModelSerializer):
    class Meta:
        abstract = True

    created_at = serializers.DateTimeField(read_only=True, required=False)
    updated_at = serializers.DateTimeField(read_only=True, required=False)


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


class UserStoreSerializer(TimestampedModelSerializer):
    class Meta:
        model = UserStore
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "banner",
            "description",
            "return_policy",
            "shipping_policy",
            "website",
        ] + get_timestamp_fields(UserStore)
        read_only_fields = ["id", "slug"] + get_timestamp_fields(UserStore)


class UserRatingSerializer(TimestampedModelSerializer):
    from_user = serializers.PrimaryKeyRelatedField(read_only=True)
    to_user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = UserRating
        fields = [
            "id",
            "transaction",
            "from_user",
            "to_user",
            "rating",
            "comment",
        ] + get_timestamp_fields(UserRating)
        read_only_fields = [
            "id",
            "transaction",
            "from_user",
            "to_user",
        ] + get_timestamp_fields(UserRating)


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
            "profile_picture",
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

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "user_type",
            "verification_status",
            "profile",
            "store",
            "addresses",
            "received_ratings",
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
            if (
                hasattr(instance, "userprofile")
                and instance.userprofile.profile_picture
            ):
                data["profile_picture"] = instance.userprofile.profile_picture.url
            else:
                data["profile_picture"] = None
        except (ValueError, AttributeError):
            data["profile_picture"] = None
        if getattr(instance, "user_type", None) == "BUYER":
            data.pop("received_ratings", None)
            data.pop("store", None)
        return data


class PublicUserProfileSerializer(serializers.ModelSerializer):
    # keep the computed fields you’re happy sharing
    average_rating = serializers.FloatField(read_only=True)
    verified_status = serializers.CharField(read_only=True)
    total_sales = serializers.IntegerField(read_only=True)
    total_purchases = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "display_name",
            "profile_picture",
            "bio",
            "country",
            "city",
            "member_since",
            "average_rating",
            "verified_status",
            "total_sales",
            "total_purchases",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            if (
                hasattr(instance, "userprofile")
                and instance.userprofile.profile_picture
            ):
                data["profile_picture"] = instance.userprofile.profile_picture.url
            else:
                data["profile_picture"] = None
        except (ValueError, AttributeError):
            data["profile_picture"] = None

        return data


class PublicUserSerializer(serializers.ModelSerializer):
    """Only the fields you’re okay exposing to others."""

    profile = PublicUserProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "profile"]
        # no email, no addresses, no private store, no ratings…


class CustomTokenObtainSerializer(TokenObtainPairSerializer):
    """
    Custom serializer for JWT token generation.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims to token
        token["user_type"] = user.user_type
        token["verification_status"] = user.verification_status
        token["email"] = user.email

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Add extra response data
        user = self.user
        data["user_id"] = str(user.id)
        data["email"] = user.email
        data["user_type"] = user.user_type
        data["verification_status"] = user.verification_status
        data["first_name"] = user.first_name
        data["last_name"] = user.last_name

        return data

# users/api/serializers.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.users.models import CustomUser, UserProfile


User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "bio",
            "address",
            "profile_picture",
            "phone_number",
            "rating",
            "total_reviews",
            "is_featured",
            "social_links",
        ]
        read_only_fields = ["id", "rating", "total_reviews", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""

    profile = UserProfileSerializer()

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
        ]
        read_only_fields = ["id", "verification_status", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        # Extract nested data
        profile_data = validated_data.pop("profile", None)

        # Update the user instance with remaining data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update nested profile if data was provided
        if profile_data and hasattr(instance, "profile"):
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        instance.save()
        return instance


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

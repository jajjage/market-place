from decimal import Decimal
from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from .models import Brand, BrandRequest, BrandVariant


class BrandListSerializer(TimestampedModelSerializer):
    """Lightweight serializer for brand lists"""

    social_media_data = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(
        source="cached_product_count",
        max_value=100,  # ✅ Integer
        min_value=1,
        read_only=True,
    )
    average_rating = serializers.DecimalField(
        source="cached_average_rating",
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        read_only=True,
    )

    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "country_of_origin",
            "is_verified",
            "is_featured",
            "product_count",
            "average_rating",
            "social_media_data",
        ]

    def get_social_media_data(self, obj) -> dict:
        # obj.social_media is already a dict because JSONField → Python dict
        return obj.social_media or {}


class BrandDetailSerializer(TimestampedModelSerializer):
    stats = serializers.SerializerMethodField()
    social_links = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        exclude = ["cached_product_count", "cached_average_rating", "stats_updated_at"]

    def get_stats(self, obj) -> dict:
        return obj.get_stats()

    def get_social_links(self, obj) -> list:
        return [
            {"platform": platform, "url": url}
            for platform, url in obj.social_media.items()
            if url
        ]


class BrandCreateSerializer(TimestampedModelSerializer):
    """Serializer for creating brands (admin only)"""

    class Meta:
        model = Brand
        exclude = ["cached_product_count", "cached_average_rating", "stats_updated_at"]

    def validate_name(self, value):
        if Brand.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Brand with this name already exists")
        return value


class BrandRequestSerializer(TimestampedModelSerializer):
    """Serializer for brand requests"""

    requested_by_username = serializers.CharField(
        source="requested_by.username", read_only=True
    )

    class Meta:
        model = BrandRequest
        fields = "__all__"
        read_only_fields = ["requested_by", "status", "processed_by", "created_brand"]


class BrandVariantSerializer(TimestampedModelSerializer):
    """Serializer for brand variants"""

    class Meta:
        model = BrandVariant
        fields = "__all__"
        read_only_fields = ["brand", "created_by", "is_auto_generated"]

    def validate(self, data):
        # Validate language and region codes
        if len(data["language_code"]) != 2:
            raise serializers.ValidationError(
                "Language code must be 2 characters (ISO 639-1)"
            )

        if data.get("region_code") and len(data["region_code"]) != 2:
            raise serializers.ValidationError(
                "Region code must be 2 characters (ISO 3166-1)"
            )

        return data

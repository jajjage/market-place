from rest_framework import serializers
from .models import Brand, BrandRequest, BrandVariant


class BrandListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for brand lists"""

    product_count = serializers.IntegerField(
        source="cached_product_count", read_only=True
    )
    average_rating = serializers.DecimalField(
        source="cached_average_rating", max_digits=3, decimal_places=2, read_only=True
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
        ]


class BrandDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single brand view"""

    stats = serializers.SerializerMethodField()
    social_links = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        exclude = ["cached_product_count", "cached_average_rating", "stats_updated_at"]

    def get_stats(self, obj):
        return obj.get_stats()

    def get_social_links(self, obj):
        return [
            {"platform": platform, "url": url}
            for platform, url in obj.social_media.items()
            if url
        ]


class BrandCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating brands (admin only)"""

    class Meta:
        model = Brand
        exclude = ["cached_product_count", "cached_average_rating", "stats_updated_at"]

    def validate_name(self, value):
        if Brand.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Brand with this name already exists")
        return value


class BrandRequestSerializer(serializers.ModelSerializer):
    """Serializer for brand requests"""

    requested_by_username = serializers.CharField(
        source="requested_by.username", read_only=True
    )

    class Meta:
        model = BrandRequest
        fields = "__all__"
        read_only_fields = ["requested_by", "status", "processed_by", "created_brand"]


class BrandVariantSerializer(serializers.ModelSerializer):
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

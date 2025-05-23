from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from apps.products.models.product_metadata import ProductMeta


class ProductMetaSerializer(TimestampedModelSerializer):
    """Serializer for product metadata."""

    class Meta:
        model = ProductMeta
        fields = [
            "id",
            "product",
            "views_count",
            "featured",
            "seo_keywords",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["views_count"]


class ProductMetaWriteSerializer(TimestampedModelSerializer):
    """Serializer for creating/updating product metadata."""

    class Meta:
        model = ProductMeta
        fields = ["product", "featured", "seo_keywords"]

    def validate_seo_keywords(self, value):
        """
        Validate SEO keywords format and length.
        """
        if value:
            # Remove extra spaces
            value = " ".join(value.split())

            # Check if keywords are comma-separated
            keywords = [k.strip() for k in value.split(",")]

            # Check if any individual keyword is too long
            max_keyword_length = 50
            for keyword in keywords:
                if len(keyword) > max_keyword_length:
                    raise serializers.ValidationError(
                        f"Individual keywords should not exceed {max_keyword_length} characters."
                    )

            # Check if too many keywords
            max_keywords = 10
            if len(keywords) > max_keywords:
                raise serializers.ValidationError(
                    f"Too many keywords. Maximum is {max_keywords}."
                )

        return value


class ProductMetaStatsSerializer(TimestampedModelSerializer):
    """Serializer for product metadata statistics."""

    product_title = serializers.CharField(source="product.title", read_only=True)

    class Meta:
        model = ProductMeta
        fields = [
            "id",
            "product",
            "product_title",
            "views_count",
            "featured",
            "created_at",
            "updated_at",
        ]


class ProductMetaUpdateViewsSerializer(TimestampedModelSerializer):
    """Serializer for incrementing product view count."""

    class Meta:
        model = ProductMeta
        fields = ["views_count"]
        read_only_fields = ["views_count"]

    def update(self, instance, validated_data):
        """Increment the views count."""
        instance.views_count += 1
        instance.save(update_fields=["views_count", "updated_at"])
        return instance


class FeaturedProductMetaSerializer(TimestampedModelSerializer):
    """Serializer for featured products metadata."""

    product_title = serializers.CharField(source="product.title", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductMeta
        fields = [
            "id",
            "product",
            "product_title",
            "product_price",
            "product_image",
            "views_count",
            "featured",
            "created_at",
        ]

    def get_product_image(self, obj):
        """Get the primary image URL for the product."""
        request = self.context.get("request")
        primary_image = (
            obj.product.images.filter(is_primary=True).first()
            or obj.product.images.first()
        )

        if request and primary_image and primary_image.image:
            return request.build_absolute_uri(primary_image.image.url)
        return None

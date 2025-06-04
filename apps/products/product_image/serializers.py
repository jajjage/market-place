from rest_framework import serializers
from .models import ProductImage, ProductImageVariant


class ProductImageVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImageVariant
        fields = ["id", "name", "width", "height", "quality"]


class ProductImageSerializer(serializers.ModelSerializer):
    variant = ProductImageVariantSerializer(read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image_url",
            "alt_text",
            "is_primary",
            "display_order",
            "variant",
            "created_at",
            "file_size_mb",
            "dimensions",
        ]

    def get_file_size_mb(self, obj):
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0

    def get_dimensions(self, obj):
        return {"width": obj.width, "height": obj.height}


class ProductImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(default=False)
    display_order = serializers.IntegerField(default=0, min_value=0)
    variant_name = serializers.CharField(required=False, allow_blank=True)

    def validate_image(self, value):
        # Additional validation for image field
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Image size cannot exceed {max_size // (1024 * 1024)}MB"
            )

        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/gif",
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid image type. Allowed: {', '.join(allowed_types)}"
            )

        return value

    def validate_variant_name(self, value):
        if (
            value
            and not ProductImageVariant.objects.filter(
                name=value, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError("Invalid variant name")
        return value


class ProductImageCreateSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(required=False)

    class Meta:
        model = ProductImage
        fields = [
            "image_url",
            "alt_text",
            "is_primary",
            "display_order",
            "variant_name",
        ]

    def validate_variant_name(self, value):
        if (
            value
            and not ProductImageVariant.objects.filter(
                name=value, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError("Invalid variant name")
        return value


class ProductImageBulkUploadSerializer(serializers.Serializer):
    images = ProductImageUploadSerializer(many=True)

    def validate_images(self, value):
        if len(value) > 5:  # Limit bulk uploads to 5 images
            raise serializers.ValidationError("Maximum 5 images per bulk upload")
        return value

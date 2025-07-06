from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from .models import ProductImage, ProductImageVariant


class ProductImageVariantSerializer(TimestampedModelSerializer):
    """Serializer for ProductImageVariant - matches API response structure"""

    class Meta:
        model = ProductImageVariant
        fields = ["id", "name", "width", "height", "quality", "is_active"]
        read_only_fields = ["id"]


class ProductImageSerializer(TimestampedModelSerializer):
    """Main serializer for ProductImage - matches API response example"""

    variant = ProductImageVariantSerializer(read_only=True)
    file_size = serializers.IntegerField(
        max_value=1000, min_value=1, read_only=True  # Use int for integer fields
    )  # Keep as bytes for accuracy
    dimensions = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image_url",
            "alt_text",
            "is_primary",
            "display_order",
            "variant",
            "file_size",
            "dimensions",
            "is_active",
            "created_by_user",
        ]
        read_only_fields = ["id", "file_size", "dimensions"]

    def get_dimensions(self, obj) -> str:
        """Return dimensions as string format matching API example"""
        if obj.width and obj.height:
            return f"{obj.width}x{obj.height}"
        return ""

    def get_image_url(self, obj) -> str | None:
        request = self.context.get("request")
        if request and obj.image_url:
            return request.build_absolute_uri(obj.image_url)
        return None


class ProductImageCreateSerializer(TimestampedModelSerializer):
    """Serializer for creating ProductImage instances"""

    variant_id = serializers.IntegerField(
        max_value=1000,  # Use int for integer fields
        min_value=1,
        required=False,
        allow_null=True,
    )
    variant_name = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    class Meta:
        model = ProductImage
        fields = [
            "product",
            "image_url",
            "alt_text",
            "is_primary",
            "display_order",
            "variant_id",
            "variant_name",
            "file_path",
            "file_size",
            "width",
            "height",
            "created_by_user",
        ]

    def validate(self, data):
        """Ensure either variant_id or variant_name is provided, not both"""
        variant_id = data.get("variant_id")
        variant_name = data.get("variant_name")

        if variant_id and variant_name:
            raise serializers.ValidationError(
                "Provide either variant_id or variant_name, not both"
            )

        return data

    def validate_variant_name(self, value):
        """Validate variant_name exists and is active"""
        if (
            value
            and not ProductImageVariant.objects.filter(
                name=value, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError(
                f"No active variant found with name '{value}'"
            )
        return value

    def validate_variant_id(self, value):
        """Validate variant_id exists and is active"""
        if (
            value
            and not ProductImageVariant.objects.filter(
                id=value, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError(
                f"No active variant found with id '{value}'"
            )
        return value

    def create(self, validated_data):
        """Handle variant_name to variant_id conversion during creation"""
        variant_name = validated_data.pop("variant_name", None)

        if variant_name:
            try:
                variant = ProductImageVariant.objects.get(
                    name=variant_name, is_active=True
                )
                validated_data["variant_id"] = variant.id
            except ProductImageVariant.DoesNotExist:
                raise serializers.ValidationError(
                    f"Variant '{variant_name}' does not exist"
                )

        return super().create(validated_data)


class ProductImageUploadSerializer(serializers.Serializer):
    """Serializer for handling image file uploads"""

    image = serializers.ImageField(required=True)
    product_id = serializers.UUIDField(required=True)
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(default=False)
    display_order = serializers.IntegerField(
        default=0, max_value=1000, min_value=1  # Use int for integer fields
    )
    variant_name = serializers.CharField(required=False, allow_blank=True)
    created_by_user = serializers.BooleanField(
        default=True
    )  # Uploads are typically user-generated

    def validate_image(self, value):
        """Validate image file size and type"""
        # File size validation
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Image size cannot exceed {max_size // (1024 * 1024)}MB. "
                f"Current size: {round(value.size / (1024 * 1024), 2)}MB"
            )

        # File type validation
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/gif",
        ]
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Invalid image type '{value.content_type}'. "
                f"Allowed types: {', '.join(allowed_types)}"
            )

        return value

    def validate_variant_name(self, value):
        """Validate variant name exists and is active"""
        if (
            value
            and not ProductImageVariant.objects.filter(
                name=value, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError(
                f"Invalid variant name '{value}'. Check available variants."
            )
        return value


class ProductImageBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creating multiple product images"""

    images = ProductImageCreateSerializer(many=True)
    product_id = serializers.UUIDField()

    def validate_images(self, value):
        """Validate bulk image creation limits"""
        if not value:
            raise serializers.ValidationError("At least one image is required")

        if len(value) > 10:  # Reasonable limit for bulk operations
            raise serializers.ValidationError(
                f"Maximum 10 images per bulk operation. Provided: {len(value)}"
            )

        # Check for duplicate display_orders
        display_orders = [img.get("display_order", 0) for img in value]
        if len(display_orders) != len(set(display_orders)):
            raise serializers.ValidationError(
                "Duplicate display_order values found in images"
            )

        # Ensure only one primary image
        primary_count = sum(1 for img in value if img.get("is_primary", False))
        if primary_count > 1:
            raise serializers.ValidationError("Only one image can be marked as primary")

        return value

    def validate_product_id(self, value):
        """Validate product exists"""
        from apps.products.product_base.models import Product  # Avoid circular import

        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Product with id {value} does not exist")
        return value

    def create(self, validated_data):
        """Create multiple ProductImage instances"""
        images_data = validated_data["images"]
        product_id = validated_data["product_id"]

        created_images = []
        for image_data in images_data:
            image_data["product_id"] = product_id
            serializer = ProductImageCreateSerializer(data=image_data)
            serializer.is_valid(raise_exception=True)
            created_images.append(serializer.save())

        return created_images


class ProductImageUpdateSerializer(TimestampedModelSerializer):
    """Serializer for updating existing ProductImage instances"""

    variant_name = serializers.CharField(
        required=False, allow_blank=True, write_only=True
    )

    class Meta:
        model = ProductImage
        fields = [
            "alt_text",
            "is_primary",
            "display_order",
            "variant_id",
            "variant_name",
            "is_active",
        ]

    def validate_variant_name(self, value):
        """Validate variant name exists and is active"""
        if (
            value
            and not ProductImageVariant.objects.filter(
                name=value, is_active=True
            ).exists()
        ):
            raise serializers.ValidationError(
                f"No active variant found with name '{value}'"
            )
        return value

    def update(self, instance, validated_data):
        """Handle variant_name to variant_id conversion during update"""
        variant_name = validated_data.pop("variant_name", None)

        if variant_name:
            try:
                variant = ProductImageVariant.objects.get(
                    name=variant_name, is_active=True
                )
                validated_data["variant_id"] = variant.id
            except ProductImageVariant.DoesNotExist:
                raise serializers.ValidationError(
                    f"Variant '{variant_name}' does not exist"
                )

        return super().update(instance, validated_data)


class ProductImageDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer with all fields for admin/detailed views"""

    variant = ProductImageVariantSerializer(read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()
    product_title = serializers.CharField(source="product.title", read_only=True)

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "product",
            "product_title",
            "image_url",
            "alt_text",
            "is_primary",
            "is_active",
            "display_order",
            "variant",
            "created_by_user",
            "file_path",
            "file_size",
            "file_size_mb",
            "width",
            "height",
            "dimensions",
            "created_at",
            "updated_at",
        ]

    def get_file_size_mb(self, obj):
        """Convert file size to MB for human-readable display"""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0

    def get_dimensions(self, obj) -> str:
        """Return dimensions as formatted string"""
        if obj.width and obj.height:
            return f"{obj.width}x{obj.height}"
        return ""


# Example usage serializers for specific API endpoints


class ProductImagesListSerializer(serializers.Serializer):
    """Serializer for listing all images for a product"""

    product_id = serializers.UUIDField()
    images = ProductImageSerializer(many=True, read_only=True)

    def to_representation(self, instance):
        """Custom representation matching the API example format"""
        return {
            "product_id": instance["product_id"],
            "images": ProductImageSerializer(instance["images"], many=True).data,
        }


class ProductImageBulkUploadSerializer(serializers.Serializer):
    images = ProductImageUploadSerializer(many=True)

    def validate_images(self, value):
        if len(value) > 5:  # Limit bulk uploads to 5 images
            raise serializers.ValidationError("Maximum 5 images per bulk upload")
        return value

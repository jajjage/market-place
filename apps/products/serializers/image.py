from rest_framework import serializers
from django.conf import settings

from apps.core.serializers import TimestampedModelSerializer
from apps.products.models.product_image import ProductImage


class ProductImageListSerializer(TimestampedModelSerializer):
    """Serializer for listing product images."""

    image_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "product",
            "image_url",
            "image_thumbnail",
            "is_primary",
            "display_order",
            "created_at",
        ]

    def get_image_thumbnail(self, obj):
        """Get thumbnail URL if using a thumbnail library."""
        request = self.context.get("request")
        if request and obj.image:
            # If using a thumbnail library like sorl-thumbnail or easy-thumbnails
            # You could generate a thumbnail here
            # For now just return the main image URL
            return request.build_absolute_uri(obj.image.url)
        return None

    def to_representation(self, instance):
        request = self.context.get("request")
        return {
            "id": str(instance.id),
            "url": (
                request.build_absolute_uri(instance.image_url)
                if request
                else instance.image_url
            ),
            "alt": instance.alt_text or "",
            "is_primary": instance.order == 0,
        }


class ProductImageDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for a single product image."""

    image_thumbnail = serializers.SerializerMethodField()
    image_size = serializers.SerializerMethodField()
    image_dimensions = serializers.SerializerMethodField()
    product_title = serializers.CharField(source="product.title", read_only=True)

    class Meta:
        model = ProductImage
        fields = [
            "id",
            "product",
            "product_title",
            "image_url",
            "image_thumbnail",
            "image_size",
            "image_dimensions",
            "is_primary",
            "display_order",
            "alt_text",
            "created_at",
            "updated_at",
        ]

    def get_image_thumbnail(self, obj):
        """Get thumbnail URL if using a thumbnail library."""
        request = self.context.get("request")
        if request and obj.image:
            # If using a thumbnail library like sorl-thumbnail or easy-thumbnails
            # You could generate a thumbnail here
            # For now just return the main image URL
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_image_size(self, obj):
        """Get image file size in bytes."""
        if obj.image and hasattr(obj.image, "size"):
            return obj.image.size
        return None

    def get_image_dimensions(self, obj):
        """Get image dimensions."""
        if obj.image and hasattr(obj.image, "width") and hasattr(obj.image, "height"):
            return {"width": obj.image.width, "height": obj.image.height}
        return None

    def to_representation(self, instance):
        request = self.context.get("request")
        return {
            "id": str(instance.id),
            "url": (
                request.build_absolute_uri(instance.image_url)
                if request
                else instance.image_url
            ),
            "alt": instance.alt_text or "",
            "is_primary": instance.display_order == 0,
        }


class ProductImageWriteSerializer(TimestampedModelSerializer):
    """Serializer for creating/updating product images."""

    class Meta:
        model = ProductImage
        fields = ["product", "image_url", "is_primary", "display_order"]

    def validate_image(self, value):
        """
        Validate image size and dimensions.
        """
        # Check file size
        max_size = getattr(
            settings, "MAX_PRODUCT_IMAGE_SIZE", 5 * 1024 * 1024
        )  # Default 5MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Image file too large. Maximum size is {max_size / 1024 / 1024:.1f}MB."
            )

        # You could also validate dimensions, format, etc.

        return value

    def validate(self, data):
        """
        Custom validation for the image.
        - If setting this image as primary, unset primary on other images
        """
        if data.get("is_primary", False):
            product = (
                data.get("product") or self.instance.product if self.instance else None
            )
            if product:
                # If this is an update and we're making this image primary,
                # we'll handle setting other images as non-primary in the view
                pass

        return data


class ProductImageBulkCreateSerializer(serializers.ListSerializer):
    """Serializer for bulk creating multiple product images."""

    child = ProductImageWriteSerializer()

    def create(self, validated_data):
        """Create multiple images at once."""
        images = [ProductImage(**item) for item in validated_data]
        return ProductImage.objects.bulk_create(images)


class ProductImageOrderUpdateSerializer(serializers.Serializer):
    """Serializer for updating the display order of multiple images."""

    image_orders = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField())
    )

    def validate_image_orders(self, value):
        """Validate that all image IDs exist."""
        image_ids = [item.get("id") for item in value if "id" in item]
        if not image_ids:
            raise serializers.ValidationError("No image IDs provided.")

        # Check if all images exist
        existing_images = ProductImage.objects.filter(id__in=image_ids)
        if len(existing_images) != len(image_ids):
            raise serializers.ValidationError("One or more image IDs are invalid.")

        return value

    def save(self):
        """Update the display order of multiple images."""
        image_orders = self.validated_data.get("image_orders", [])

        for order_data in image_orders:
            image_id = order_data.get("id")
            new_order = order_data.get("order")

            if image_id and new_order is not None:
                ProductImage.objects.filter(id=image_id).update(display_order=new_order)

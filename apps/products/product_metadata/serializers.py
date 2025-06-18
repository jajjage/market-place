# apps/products/product_meta/serializers.py

from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from apps.products.product_base.models import Product
from apps.products.product_image.services import ProductImageService
from .models import ProductMeta
from .services import ProductMetaService  # Import from service layer


class ProductMetaWriteSerializer(TimestampedModelSerializer):
    """
    Serializer for creating/updating product metadata.
    Used by admins.
    """

    # Make the product field write-only and accept just the ID
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = ProductMeta
        fields = ["product", "seo_keywords"]

    def validate_seo_keywords(self, value):
        """
        Validate SEO keywords by calling the centralized service function.
        """
        try:
            # Re-use the business logic from the service layer
            return ProductMetaService.validate_seo_keywords_format(value)
        except ValueError as e:
            # Convert the service's ValueError to DRF's validation error
            raise serializers.ValidationError(str(e))


class ProductMetaDetailSerializer(TimestampedModelSerializer):
    """
    Detailed serializer for product metadata, including related product info.
    Used for public-facing endpoints like stats, featured, popular, etc.
    """

    # Pull in useful fields from the related Product model
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.SlugField(source="product.slug", read_only=True)
    product_shortcode = serializers.SlugField(
        source="product.shortcode", read_only=True
    )
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )
    product_is_featured = serializers.BooleanField(
        source="product.is_featured", read_only=True
    )
    product_image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductMeta
        fields = [
            "id",
            "product",  # The product ID
            "product_title",
            "product_slug",
            "product_shortcode",
            "product_price",
            "product_is_featured",
            "product_image_url",
            "views_count",
            "seo_keywords",
        ]
        read_only_fields = fields  # This serializer is for reading only

    def get_product_image_url(self, obj):
        """
        Get the primary image URL for the product.
        This is efficient because the view will prefetch the images.
        """
        request = self.context.get("request")
        # Access pre-fetched images if they exist
        if hasattr(obj.product, "images") and obj.product.images:
            primary_image = ProductImageService.get_primary_image(obj.product.id)

            if primary_image and primary_image.image_url:
                # Try to build absolute URL if request is available
                if request:
                    return request.build_absolute_uri(primary_image.image_url)
                else:
                    # Fallback to relative URL or build manually
                    return primary_image.image_url
                    # Or build manually: f"http://your-domain.com{primary_image.image_url}"

        return None

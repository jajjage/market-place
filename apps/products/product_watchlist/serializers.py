from rest_framework import serializers

from apps.core.serializers import (
    BreadcrumbSerializer,
    TimestampedModelSerializer,
    UserShortSerializer,
)
from apps.core.utils.breadcrumbs import BreadcrumbService
from .models import ProductWatchlistItem


class ProductWatchlistItemListSerializer(TimestampedModelSerializer):
    """Serializer for listing watchlist items."""

    user = UserShortSerializer(read_only=True)
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = ProductWatchlistItem
        fields = [
            "id",
            "user",
            "product",
            "product_title",
            "product_price",
            "product_image",
            "added_at",
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


class ProductWatchlistItemDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for a single watchlist item."""

    breadcrumbs = serializers.SerializerMethodField()
    user = UserShortSerializer(read_only=True)
    product_details = serializers.SerializerMethodField()

    class Meta:
        model = ProductWatchlistItem
        fields = ["id", "user", "product", "product_details", "added_at"]

    def get_product_details(self, obj):
        """Get detailed information about the watched product."""
        request = self.context.get("request")
        primary_image = (
            obj.product.images.filter(is_primary=True).first()
            or obj.product.images.first()
        )

        details = {
            "id": obj.product.id,
            "title": obj.product.title,
            "price": obj.product.price,
            "description": (
                obj.product.description[:150] + "..."
                if len(obj.product.description) > 150
                else obj.product.description
            ),
            "status": obj.product.status,
            "is_active": obj.product.is_active,
            "slug": obj.product.slug,
            "short_code": (
                obj.product.short_code if hasattr(obj.product, "short_code") else None
            ),
        }

        if request and primary_image and primary_image.image:
            details["image_url"] = request.build_absolute_uri(primary_image.image.url)

        return details

    def get_breadcrumbs(self, obj):
        breadcrumb_data = BreadcrumbService.generate_watchlist_breadcrumbs(obj)
        return BreadcrumbSerializer(breadcrumb_data, many=True).data


class ProductWatchlistItemCreateSerializer(TimestampedModelSerializer):
    """Serializer for adding a product to watchlist."""

    class Meta:
        model = ProductWatchlistItem
        fields = ["product"]

    def validate_product(self, value):
        """
        Validate that:
        1. The product exists and is active
        2. The user isn't already watching this product
        """
        user = self.context["request"].user

        # Check if product is active
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot add inactive product to watchlist."
            )

        # Check if already in watchlist
        if ProductWatchlistItem.objects.filter(user=user, product=value).exists():
            raise serializers.ValidationError(
                "This product is already in your watchlist."
            )

        return value

    def create(self, validated_data):
        """Add the current user to the watchlist item."""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ProductWatchlistBulkSerializer(serializers.Serializer):
    """Serializer for bulk watchlist operations."""

    product_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action = serializers.ChoiceField(choices=["add", "remove"])

    def validate_product_ids(self, value):
        """Validate that all product IDs exist."""
        from apps.products.product_base.models import Product

        # Check if all products exist
        existing_products = Product.objects.filter(id__in=value, is_active=True)
        if len(existing_products) != len(value):
            raise serializers.ValidationError(
                "One or more product IDs are invalid or inactive."
            )

        return value

    def save(self):
        """Perform bulk add or remove operations."""
        user = self.context["request"].user
        product_ids = self.validated_data["product_ids"]
        action = self.validated_data["action"]

        from apps.products.product_base.models import Product

        if action == "add":
            # Get products that aren't already in the watchlist
            existing_watchlist = ProductWatchlistItem.objects.filter(
                user=user, product_id__in=product_ids
            ).values_list("product_id", flat=True)

            products_to_add = Product.objects.filter(id__in=product_ids).exclude(
                id__in=existing_watchlist
            )

            # Bulk create new watchlist items
            watchlist_items = [
                ProductWatchlistItem(user=user, product=product)
                for product in products_to_add
            ]

            if watchlist_items:
                return ProductWatchlistItem.objects.bulk_create(watchlist_items)

        elif action == "remove":
            # Delete watchlist items for these products
            items_to_delete = ProductWatchlistItem.objects.filter(
                user=user, product_id__in=product_ids
            )

            count = items_to_delete.count()
            items_to_delete.delete()

            return {"removed_count": count}

        return {"message": "No changes made"}


class WatchlistStatsSerializer(serializers.Serializer):
    """Serializer for watchlist statistics."""

    total_items = serializers.IntegerField()
    recently_added = serializers.ListField(child=serializers.IntegerField())
    most_watched_categories = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField())
    )

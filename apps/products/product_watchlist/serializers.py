from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model

# from apps.core.utils.import_resolver import resolver
from apps.core.serializers import TimestampedModelSerializer, UserShortSerializer
from apps.products.product_base.models import Product
from apps.products.product_image.services import ProductImageService

from .models import ProductWatchlistItem

User = get_user_model()


class WatchlistProductListSerializer(TimestampedModelSerializer):
    """
    Serializer for listing products with essential information.
    Optimized for displaying products in listings.
    """

    brand_name = serializers.SerializerMethodField(read_only=True)
    originalPrice = serializers.DecimalField(
        source="original_price",
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )
    escrowFee = serializers.DecimalField(
        source="escrow_fee",
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )

    seller = serializers.SerializerMethodField()
    # Use direct annotation fields instead of nested serializer for better performance
    ratings = serializers.SerializerMethodField()

    category_name = serializers.CharField(source="category.name", read_only=True)
    condition_name = serializers.CharField(source="condition.name", read_only=True)
    image_url = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "price",
            "originalPrice",
            "currency",
            "category_name",
            "condition_name",
            "requires_inspection",
            "is_active",
            "is_featured",
            "status",
            "slug",
            "ratings",
            "short_code",
            "seller",
            "escrowFee",
            "location",
            "description",
            "image_url",
            "discount_percent",
            "brand_name",
        ]

    def get_brand_name(self, obj) -> str | None:
        return obj.brand.name

    def get_seller(self, obj) -> dict | None:
        profile_obj = obj.seller
        return UserShortSerializer(profile_obj, context=self.context).data

    def get_image_url(self, obj) -> str | None:
        request = self.context.get("request")
        primary_image = ProductImageService.get_primary_image(obj.id)
        if primary_image and primary_image.image_url:
            # Try to build absolute URL if request is available
            if request:
                return request.build_absolute_uri(primary_image.image_url)
            else:
                # Fallback to relative URL or build manually
                return primary_image.image_url
                # Or build manually: f"http://your-domain.com{primary_image.image_url}"

        return None

    def get_discount_percent(self, obj) -> float:
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

    def get_ratings(self, obj) -> dict:
        """Get ratings from annotated fields"""
        return {
            "average": getattr(obj, "avg_rating_db", 0),
            "total": getattr(obj, "ratings_count_db", 0),
            "verified_count": getattr(obj, "verified_ratings_count", 0),
            "distribution": {
                "5": getattr(obj, "five_star_count", 0),
                "4": getattr(obj, "four_star_count", 0),
                "3": getattr(obj, "three_star_count", 0),
                "2": getattr(obj, "two_star_count", 0),
                "1": getattr(obj, "one_star_count", 0),
            },
        }


class ProductWatchlistItemCreateSerializer(TimestampedModelSerializer):
    """Serializer for creating watchlist items."""

    product_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ProductWatchlistItem
        fields = ["product_id"]

    def validate_product_id(self, value):
        """Validate that the product exists and is active."""
        try:
            # Just validate the product exists, but return the UUID value
            Product.objects.get(id=value, is_active=True, status="active")
            return value  # Return the UUID, not the product object
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive")

    def create(self, validated_data):
        """Create watchlist item with proper user assignment."""
        print(validated_data)

        # Get the product object using the validated product_id
        product = Product.objects.get(id=validated_data.pop("product_id"))

        validated_data["user"] = self.context["request"].user
        validated_data["product"] = product

        return super().create(validated_data)


class ProductWatchlistItemListSerializer(TimestampedModelSerializer):
    """Serializer for listing watchlist items with minimal product info."""

    product = serializers.SerializerMethodField()
    added_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    days_in_watchlist = serializers.SerializerMethodField()

    class Meta:
        model = ProductWatchlistItem
        fields = ["id", "product", "added_at", "days_in_watchlist"]
        read_only_fields = ["id", "added_at"]

    def get_days_in_watchlist(self, obj) -> int:
        """Calculate days since item was added to watchlist."""
        from datetime import datetime

        if obj.added_at:
            delta = datetime.now() - obj.added_at.replace(tzinfo=None)
            return delta.days
        return 0

    def get_product(self, obj) -> dict | None:
        # Try the prefetched list first
        pref = getattr(obj, "prefetched_product", None)

        if isinstance(pref, list):
            prod = pref[0] if pref else None
        elif pref is not None:
            # could be a single Product
            prod = pref
        else:
            # fallback to the FK
            prod = obj.product

        if not prod:
            return None

        return WatchlistProductListSerializer(prod, context=self.context).data


class ProductWatchlistItemDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for individual watchlist items."""

    product = WatchlistProductListSerializer(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    added_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    days_in_watchlist = serializers.SerializerMethodField()

    class Meta:
        model = ProductWatchlistItem
        fields = ["id", "user", "product", "added_at", "days_in_watchlist"]
        read_only_fields = fields

    def get_days_in_watchlist(self, obj) -> int:
        """Calculate days since item was added to watchlist."""
        from datetime import datetime

        if obj.added_at:
            delta = datetime.now() - obj.added_at.replace(tzinfo=None)
            return delta.days
        return 0


class ProductWatchlistBulkSerializer(serializers.Serializer):
    """Serializer for bulk watchlist operations."""

    OPERATION_CHOICES = [
        ("add", "Add products to watchlist"),
        ("remove", "Remove products from watchlist"),
    ]

    # product = resolver.get_model("apps.products.product_base", "Product")

    operation = serializers.ChoiceField(
        choices=OPERATION_CHOICES, help_text="Operation to perform: 'add' or 'remove'"
    )
    product_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
        help_text="List of product IDs (max 100)",
    )
    validate_products = serializers.BooleanField(
        default=True,
        help_text="Whether to validate that all products exist and are active",
    )

    def validate_product_ids(self, value):
        """Validate product IDs and remove duplicates."""
        if not value:
            raise serializers.ValidationError("At least one product ID is required")

        # Remove duplicates while preserving order
        unique_ids = list(dict.fromkeys(value))

        if len(unique_ids) > 100:
            raise serializers.ValidationError(
                "Maximum 100 products allowed per operation"
            )

        return unique_ids

    def validate(self, attrs):
        """Validate the bulk operation request."""
        # product = resolver.get_model("apps.products.product_base", "Product")
        validate_products = attrs.get("validate_products", True)
        product_ids = attrs.get("product_ids", [])

        if validate_products and product_ids:
            # Check if all products exist and are active
            existing_products = set(
                Product.objects.filter(id__in=product_ids, is_active=True).values_list(
                    "id", flat=True
                )
            )

            missing_products = set(product_ids) - existing_products
            if missing_products:
                raise serializers.ValidationError(
                    {
                        "product_ids": f"Products not found or inactive: {list(missing_products)}"
                    }
                )

        return attrs


class WatchlistStatsSerializer(serializers.Serializer):
    """Serializer for watchlist statistics."""

    total_items = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    recently_added = serializers.ListField(
        child=serializers.UUIDField(), help_text="Product IDs of recently added items"
    )
    most_watched_categories = serializers.ListField(
        child=serializers.DictField(),
        help_text="Categories with highest watchlist counts",
    )
    oldest_item_date = serializers.DateTimeField(
        allow_null=True, format="%Y-%m-%d %H:%M:%S"
    )
    newest_item_date = serializers.DateTimeField(
        allow_null=True, format="%Y-%m-%d %H:%M:%S"
    )
    categories_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )

    def to_representation(self, instance):
        """Convert WatchlistStats dataclass to dict."""
        if hasattr(instance, "__dict__"):
            # Handle dataclass instance
            return {
                "total_items": instance.total_items,
                "recently_added": [str(pid) for pid in instance.recently_added],
                "most_watched_categories": instance.most_watched_categories,
                "oldest_item_date": instance.oldest_item_date,
                "newest_item_date": instance.newest_item_date,
                "categories_count": instance.categories_count,
            }
        return super().to_representation(instance)


class WatchlistInsightsSerializer(serializers.Serializer):
    """Serializer for advanced watchlist insights."""

    total_items = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    recent_activity = serializers.DictField(help_text="Recent activity breakdown")
    category_distribution = serializers.ListField(
        child=serializers.DictField(), help_text="Distribution of products by category"
    )
    activity_summary = serializers.CharField(
        help_text="Human-readable activity summary"
    )
    recommendations = serializers.ListField(
        child=serializers.CharField(), help_text="Personalized recommendations"
    )


class WatchlistOperationResultSerializer(serializers.Serializer):
    """Serializer for watchlist operation results."""

    success = serializers.BooleanField()
    message = serializers.CharField()
    status = serializers.CharField()
    affected_count = serializers.IntegerField(
        max_value=100, min_value=1, default=0  # ✅ Integer
    )
    errors = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )

    def to_representation(self, instance):
        """Convert WatchlistOperationResult dataclass to dict."""
        if hasattr(instance, "__dict__"):
            # Handle dataclass instance
            return {
                "success": instance.success,
                "message": instance.message,
                "status": instance.status,
                "affected_count": instance.affected_count,
                "errors": instance.errors or [],
            }
        return super().to_representation(instance)


class WatchlistToggleSerializer(serializers.Serializer):
    """Serializer for toggle operations."""

    product_id = serializers.UUIDField(help_text="Product ID to toggle in watchlist")

    def validate_product_id(self, value):
        """Validate that the product exists and is active."""
        # product = resolver.get_model("apps.products.product_base", "Product")
        try:
            Product.objects.get(id=value, is_active=True)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive")


class WatchlistCheckSerializer(serializers.Serializer):
    """Serializer for checking if product is in watchlist."""

    in_watchlist = serializers.BooleanField()
    product_id = serializers.UUIDField()


class ProductWatchlistCountSerializer(serializers.Serializer):
    """Serializer for product watchlist count (staff only)."""

    product_id = serializers.UUIDField()
    watchlist_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    timestamp = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", help_text="Timestamp when count was retrieved"
    )


# Admin/Staff serializers
class WatchlistItemAdminSerializer(TimestampedModelSerializer):
    """Admin serializer with full details."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price",
        read_only=True,
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )
    category_name = serializers.CharField(
        source="product.category.name", read_only=True
    )

    class Meta:
        model = ProductWatchlistItem
        fields = [
            "id",
            "user",
            "user_email",
            "product",
            "product_name",
            "product_price",
            "category_name",
            "added_at",
        ]
        read_only_fields = fields


class WatchlistAnalyticsSerializer(serializers.Serializer):
    """Serializer for advanced analytics (staff only)."""

    total_users_with_watchlists = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    total_watchlist_items = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    average_watchlist_size = serializers.FloatField(
        max_value=5.0, min_value=0.0  # Use float for float fields
    )
    most_watched_products = serializers.ListField(child=serializers.DictField())
    watchlist_growth = serializers.DictField(help_text="Growth statistics over time")
    category_popularity = serializers.ListField(child=serializers.DictField())
    user_engagement = serializers.DictField(help_text="User engagement metrics")

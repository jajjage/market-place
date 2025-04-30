from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models.base import Product
from .models.category import Category
from .models.product_condition import ProductCondition
from .models.product_image import ProductImage
from .models.product_metadata import ProductMeta
from .models.product_watchlist import ProductWatchlistItem

User = get_user_model()


class TimestampedModelSerializer(serializers.ModelSerializer):
    """Adds created_at and updated_at fields to all serializers."""

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        abstract = True


class UserShortSerializer(TimestampedModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "created_at")


class CategorySerializer(TimestampedModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "parent", "created_at")


class ProductConditionSerializer(TimestampedModelSerializer):
    class Meta:
        model = ProductCondition
        fields = ("id", "name", "description", "created_at")


class ProductImageSerializer(TimestampedModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "is_primary", "display_order", "created_at")


class ProductMetaSerializer(TimestampedModelSerializer):
    class Meta:
        model = ProductMeta
        fields = ("views_count", "featured", "seo_keywords", "created_at")


class ProductWatchlistItemSerializer(TimestampedModelSerializer):
    user = UserShortSerializer(read_only=True)
    product = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ProductWatchlistItem
        fields = ("id", "user", "product", "added_at", "created_at")


class ProductBaseSerializer(TimestampedModelSerializer):
    """Base serializer for Product, for DRY and extensibility."""

    seller = UserShortSerializer(read_only=True)
    share_url = serializers.SerializerMethodField()
    short_code = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)
    condition = ProductConditionSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    meta = ProductMetaSerializer(read_only=True)
    watchers_count = serializers.SerializerMethodField()
    is_in_watchlist = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "price",
            "original_price",
            "discount_percentage",
            "category",
            "condition",
            "is_active",
            "inventory_count",
            "is_featured",
            "status",
            "specifications",
            "slug",
            "short_code",
            "seller",
            "images",
            "meta",
            "watchers_count",
            "is_in_watchlist",
            "created_at",
            "updated_at",
        ]

    def get_share_url(self, obj):
        return obj.get_share_url()

    def get_short_code(self, obj):
        return obj.short_code

    def get_seller(self, obj):
        first_name = obj.seller.first_name
        last_name = obj.seller.last_name

        return f"{first_name}  {last_name}"

    def to_representation(self, instance):
        print("Using ProductDetailSerializer")  # or ProductSerializer
        return super().to_representation(instance)

    def get_watchers_count(self, obj):
        return obj.watchers.count()

    def get_is_in_watchlist(self, obj):
        user = self.context.get("request").user
        if user.is_authenticated:
            return obj.watchers.filter(user=user).exists()
        return False


class ProductWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating products (uses IDs for relations)."""

    class Meta:
        model = Product
        fields = [
            "title",
            "description",
            "price",
            "original_price",
            "category",
            "condition",
            "is_active",
            "inventory_count",
            "is_featured",
            "status",
            "specifications",
        ]


class ProductDetailSerializer(ProductBaseSerializer):
    """For detailed product view, can be extended for escrow/transaction info."""

    pass

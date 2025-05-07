from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from apps.products.models import Product, Category, ProductCondition
from apps.products.serializers.category import CategoryDetailSerializer
from apps.products.serializers.base import TimestampedModelSerializer
from apps.products.serializers.conditions import ProductConditionDetailSerializer


class UserShortSerializer(TimestampedModelSerializer):
    """Serializer for a short representation of the user."""

    class Meta:
        model = get_user_model()
        fields = ["id", "first_name", "first_name", "last_name"]


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for creating products.
    Only title is required, other fields can be updated later.
    """

    class Meta:
        model = Product
        fields = ["id", "title"]
        read_only_fields = [
            "id",
            "seller",
            "slug",
            "short_code",
            "category",
            "condition",
        ]

    def create(self, validated_data):
        # Set the seller as current user
        validated_data["seller"] = self.context["request"].user

        # Set default values for required fields
        validated_data.setdefault("price", 0.00)
        validated_data.setdefault("description", "")

        # Get default category and condition
        # IMPORTANT: We need to query these objects first and make sure they exist
        default_category = Category.objects.first()
        if not default_category:
            raise serializers.ValidationError(
                "At least one category must exist in the system"
            )
        validated_data["category"] = default_category

        default_condition = ProductCondition.objects.first()
        if not default_condition:
            raise serializers.ValidationError(
                "At least one product condition must exist in the system"
            )
        validated_data["condition"] = default_condition

        # Create the product with minimal info
        return super().create(validated_data)


class ProductUpdateSerializer(TimestampedModelSerializer):
    """
    Serializer for updating product information.
    Allows partial updates to complete the product details.
    """

    class Meta:
        model = Product
        fields = [
            "title",
            "description",
            "price",
            "original_price",
            "currency",
            "category",
            "condition",
            "is_active",
            "in_escrow_inventory",
            "available_inventory",
            "total_inventory",
            "is_featured",
            "status",
            "specifications",
        ]

    def update(self, instance, validated_data):
        # Update slug if title changes
        if "title" in validated_data and validated_data["title"] != instance.title:
            validated_data["slug"] = slugify(validated_data["title"])

        return super().update(instance, validated_data)


class ProductListSerializer(TimestampedModelSerializer):
    """
    Serializer for listing products with essential information.
    Optimized for displaying products in listings.
    """

    seller_name = serializers.CharField(source="seller.get_full_name", read_only=True)
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
            "original_price",
            "currency",
            "category_name",
            "condition_name",
            "is_active",
            "is_featured",
            "status",
            "slug",
            "short_code",
            "seller_name",
            "image_url",
            "discount_percent",
            "in_escrow_inventory",
            "available_inventory",
            "total_inventory",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")
        primary_image = obj.images.filter(is_primary=True).first() or obj.images.first()

        if request and primary_image and primary_image.image:
            return request.build_absolute_uri(primary_image.image.url)
        return None

    def get_discount_percent(self, obj):
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0


class ProductDetailSerializer(TimestampedModelSerializer):
    """
    Detailed serializer for a single product.
    Includes all information including nested category and seller details.
    """

    seller = serializers.SerializerMethodField()
    category = CategoryDetailSerializer(read_only=True)
    condition = ProductConditionDetailSerializer(read_only=True)
    images = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    watching_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "seller",
            "title",
            "description",
            "price",
            "original_price",
            "currency",
            "category",
            "condition",
            "is_active",
            "in_escrow_inventory",
            "available_inventory",
            "total_inventory",
            "is_featured",
            "status",
            "specifications",
            "slug",
            "short_code",
            "images",
            "discount_percent",
            "watching_count",
            "created_at",
            "updated_at",
        ]

    def get_seller(self, obj):
        return {
            "id": obj.seller.id,
            "first_name": obj.seller.first_name,
            "full_name": obj.seller.get_full_name(),
            "avatar": (
                self.context.get("request").build_absolute_uri(
                    obj.seller.profile.avatar_url
                )
                if hasattr(obj.seller, "profile") and obj.seller.profile.avatar_url
                else None
            ),
        }

    def get_images(self, obj):
        request = self.context.get("request")
        images = []

        for img in obj.images.all():
            if img.image:
                images.append(
                    {
                        "id": img.id,
                        "url": request.build_absolute_uri(img.image.url),
                        "is_primary": img.is_primary,
                        "alt_text": img.alt_text or "",
                    }
                )

        return images

    def get_discount_percent(self, obj):
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

    def get_watching_count(self, obj):
        """Get the number of users watching this product"""
        return obj.watchers.count()


class ProductStatsSerializer(TimestampedModelSerializer):
    """
    Specialized serializer for collecting product statistics.
    Focused on fields useful for analytics.
    """

    seller_id = serializers.IntegerField(source="seller.id")
    seller_name = serializers.CharField(source="seller.get_full_name")
    category_id = serializers.IntegerField(source="category.id")
    category_name = serializers.CharField(source="category.name")
    condition_name = serializers.CharField(source="condition.name")
    watching_count = serializers.SerializerMethodField()
    images_count = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "seller_id",
            "seller_name",
            "title",
            "price",
            "original_price",
            "currency",
            "category_id",
            "category_name",
            "condition_name",
            "is_active",
            "is_featured",
            "status",
            "in_escrow_inventory",
            "available_inventory",
            "total_inventory",
            "watching_count",
            "images_count",
            "has_discount",
            "discount_amount",
            "discount_percent",
            "created_at",
            "updated_at",
        ]

    def get_watching_count(self, obj):
        return obj.watchers.count()

    def get_images_count(self, obj):
        return obj.images.count()

    def get_has_discount(self, obj):
        return bool(obj.original_price and obj.price < obj.original_price)

    def get_discount_amount(self, obj):
        if obj.original_price and obj.price < obj.original_price:
            return obj.original_price - obj.price
        return 0

    def get_discount_percent(self, obj):
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

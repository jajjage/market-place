from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from apps.categories.models import Category
from apps.categories.serializers import CategoryDetailSerializer
from apps.core.serializers import TimestampedModelSerializer
from apps.products.models import Product, ProductCondition
from apps.products.serializers.conditions import ProductConditionDetailSerializer
from apps.products.serializers.image import ProductImageDetailSerializer
from apps.products.serializers.ratings import ProductRatingsSerializer
from apps.products.serializers.variants import ProductVariantSerializer
from apps.users.serializers import PublicUserProfileSerializer


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
            "escrow_fee",
            "location",
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

    originalPrice = serializers.DecimalField(
        source="original_price", max_digits=10, decimal_places=2
    )
    escrowFee = serializers.DecimalField(
        source="escrow_fee", max_digits=10, decimal_places=2
    )

    seller = serializers.SerializerMethodField()
    ratings = ProductRatingsSerializer(source="*", read_only=True)

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
            "is_active",
            "is_featured",
            "status",
            "slug",
            "ratings",
            "short_code",
            "seller",
            "escrowFee",
            "location",
            "condition",
            "description",
            "image_url",
            "discount_percent",
            "in_escrow_inventory",
            "available_inventory",
            "total_inventory",
        ]

    def get_seller(self, obj):
        profile_obj = obj.seller.profile
        return PublicUserProfileSerializer(profile_obj, context=self.context).data

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

    variants = ProductVariantSerializer(many=True, read_only=True)
    variant_summary = serializers.SerializerMethodField()

    # Write-only for variant creation
    variant_combinations = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="Specific variant combinations to create",
    )

    # Alternative: Auto-generate from selected options
    auto_generate_variants = serializers.DictField(
        write_only=True,
        required=False,
        help_text="Auto-generate variants from option groups: {'color': [1,2,3], 'size': [4,5,6]}",
    )

    base_variant_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        write_only=True,
        required=False,
        help_text="Base price for auto-generated variants",
    )

    originalPrice = serializers.DecimalField(
        source="original_price", max_digits=10, decimal_places=2
    )
    escrowFee = serializers.DecimalField(
        source="escrow_fee", max_digits=10, decimal_places=2
    )
    images = ProductImageDetailSerializer(many=True, read_only=True)
    seller = serializers.SerializerMethodField()
    ratings = ProductRatingsSerializer(source="*", read_only=True)
    variants = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()
    category = CategoryDetailSerializer(read_only=True)
    condition = ProductConditionDetailSerializer(read_only=True)
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
            "originalPrice",
            "currency",
            "category",
            "condition",
            "is_active",
            "in_escrow_inventory",
            "available_inventory",
            "total_inventory",
            "is_featured",
            "status",
            "slug",
            "short_code",
            "images",
            "escrowFee",
            "location",
            "description",
            "variants",
            "variant_summary",
            "variant_combinations",
            "auto_generate_variants",
            "base_variant_price",
            "ratings",
            "details",
            "features",
            "specifications",
            "breadcrumbs",
            "discount_percent",
            "watching_count",
            "created_at",
            "updated_at",
        ]

    def get_seller(self, obj):
        profile_obj = obj.seller.profile
        return PublicUserProfileSerializer(profile_obj, context=self.context).data

    def get_variant_summary(self, obj):
        """Get variant summary with statistics"""
        return {
            "total_variants": getattr(obj, "total_variants", 0),
            "available_variants": getattr(obj, "available_variants", 0),
            "price_range": {
                "min": getattr(obj, "min_variant_price", None),
                "max": getattr(obj, "max_variant_price", None),
                "avg": getattr(obj, "avg_variant_price", None),
            },
            "total_stock": getattr(obj, "total_stock", 0),
            "variant_types": getattr(obj, "variant_types", []),
        }

    def get_discount_percent(self, obj):
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

    def get_watching_count(self, obj):
        """Get the number of users watching this product"""
        return obj.watchers.count()

    def get_variants(self, obj):
        # This would need to be implemented based on your variant logic
        # For now, returning a sample structure
        return [
            {"type": "Color", "options": ["Brown", "Black", "Tan"]},
            {"type": "Condition", "options": ["New with tags", "Like New", "Good"]},
        ]

    def get_details(self, obj):
        """Generate details list from model fields"""
        details = []

        if obj.brand:
            details.append({"label": "Brand", "value": obj.brand})
        if obj.model:
            details.append({"label": "Model", "value": obj.model})
        if obj.material:
            details.append({"label": "Material", "value": obj.material})
        if obj.color:
            details.append({"label": "Color", "value": obj.color})
        if obj.dimensions:
            details.append({"label": "Dimensions", "value": obj.dimensions})
        if obj.style:
            details.append({"label": "Style", "value": obj.style})

        details.append({"label": "Condition", "value": obj.condition.name})

        if obj.authenticity_guaranteed:
            details.append({"label": "Authenticity", "value": "Guaranteed Authentic"})

        return details

    def get_breadcrumbs(self, obj):
        # You can implement this based on your category structure
        return [
            {"name": "TrustLock", "href": "/"},
            {"name": "Fashion & Accessories", "href": "/explore?category=fashion"},
            {"name": "Women's Bags & Handbags", "href": "/explore?category=bags"},
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Convert condition object to string
        data["condition"] = instance.condition.name
        return data


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

    def get_variants(self, obj):
        # This would need to be implemented based on your variant logic
        # For now, returning a sample structure
        return [
            {"type": "Color", "options": ["Brown", "Black", "Tan"]},
            {"type": "Condition", "options": ["New with tags", "Like New", "Good"]},
        ]

    def get_details(self, obj):
        """Generate details list from model fields"""
        details = []

        if obj.brand:
            details.append({"label": "Brand", "value": obj.brand})
        if obj.model:
            details.append({"label": "Model", "value": obj.model})
        if obj.material:
            details.append({"label": "Material", "value": obj.material})
        if obj.color:
            details.append({"label": "Color", "value": obj.color})
        if obj.dimensions:
            details.append({"label": "Dimensions", "value": obj.dimensions})
        if obj.style:
            details.append({"label": "Style", "value": obj.style})

        details.append({"label": "Condition", "value": obj.condition.name})

        if obj.authenticity_guaranteed:
            details.append({"label": "Authenticity", "value": "Guaranteed Authentic"})

        return details

    def get_breadcrumbs(self, obj):
        # You can implement this based on your category structure
        return [
            {"name": "TrustLock", "href": "/"},
            {"name": "Fashion & Accessories", "href": "/explore?category=fashion"},
            {"name": "Women's Bags & Handbags", "href": "/explore?category=bags"},
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Convert condition object to string
        data["condition"] = instance.condition.name
        return data

from rest_framework import serializers
from django.utils.text import slugify
from apps.categories.models import Category
from apps.categories.serializers import (
    # CategoryDetailSerializer,
    CategorySummarySerializer,
)
from apps.core.serializers import (
    BreadcrumbSerializer,
    TimestampedModelSerializer,
    UserShortSerializer,
)
from apps.core.utils.breadcrumbs import BreadcrumbService
from apps.products.product_brand.services import BrandService
from apps.products.product_brand.models import Brand
from apps.products.product_condition.models import ProductCondition
from apps.products.product_image.services import ProductImageService
from .models import Product

from apps.products.product_condition.serializers import ProductConditionDetailSerializer
from apps.products.product_image.serializers import ProductImageSerializer

from apps.products.product_variant.serializers import ProductVariantSerializer
from apps.products.product_brand.serializers import BrandListSerializer
from apps.products.product_watchlist.serializers import (
    ProductWatchlistItemListSerializer,
)
from apps.products.product_metadata.serializers import ProductMetaDetailSerializer
from apps.products.product_detail.serializers import (
    ProductDetailSerializer as ProductExtraDetailSerializer,
)
from apps.products.product_variant.services import ProductVariantService
from apps.products.product_detail.services import ProductDetailService


class ProductCreateSerializer(TimestampedModelSerializer):
    """
    Minimal serializer for creating products.
    Only title is required, other fields can be updated later.
    """

    # Use PrimaryKeyRelatedField to accept IDs instead of instances
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), write_only=True
    )
    condition = serializers.PrimaryKeyRelatedField(
        queryset=ProductCondition.objects.all(), write_only=True
    )
    brand = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(), write_only=True
    )

    class Meta:
        model = Product
        fields = ["id", "title", "category", "condition", "brand"]
        read_only_fields = [
            "id",
            "seller",
            "slug",
            "short_code",
        ]

    def create(self, validated_data):
        # Set the seller as current user
        validated_data["seller"] = self.context["request"].user

        # Set default values for required fields
        validated_data.setdefault("price", 0.00)
        validated_data.setdefault("description", "")

        # Category and condition are already converted to instances by DRF
        if not validated_data.get("category"):
            raise serializers.ValidationError("You need to provide category")

        if not validated_data.get("condition"):
            raise serializers.ValidationError("You need to provide condition")

        if not validated_data.get("brand"):
            raise serializers.ValidationError("You need to provide condition")

        # Create the product with minimal info
        return super().create(validated_data)


class ProductUpdateSerializer(TimestampedModelSerializer):
    condition_id = serializers.PrimaryKeyRelatedField(
        source="condition",
        queryset=ProductCondition.objects.filter(is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Product
        fields = [
            "title",
            "description",
            "price",
            "status",
            "condition_id",
            "authenticity_guaranteed",
            "warranty_period",
            "original_price",
            "currency",
            "escrow_fee",
            "location",
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

    brand_name = serializers.SerializerMethodField(read_only=True)
    originalPrice = serializers.DecimalField(
        source="original_price", max_digits=10, decimal_places=2
    )
    escrowFee = serializers.DecimalField(
        source="escrow_fee", max_digits=10, decimal_places=2
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

    def get_brand_name(self, obj):
        return obj.brand.name

    def get_seller(self, obj):
        profile_obj = obj.seller
        return UserShortSerializer(profile_obj, context=self.context).data

    def get_image_url(self, obj):
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

    def get_discount_percent(self, obj):
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

    def get_ratings(self, obj):
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


class ProductDetailSerializer(TimestampedModelSerializer):
    """
    Detailed serializer for a single product.
    Includes all information including nested category and seller details.
    """

    # brand_detail = serializers.SerializerMethodField(read_only=True)
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
    images = ProductImageSerializer(many=True, read_only=True)
    seller = serializers.SerializerMethodField()
    # Use direct annotation fields for ratings
    ratings = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()
    category = CategorySummarySerializer(read_only=True)
    total_views = serializers.IntegerField(source="meta.views_count", read_only=True)
    user_has_purchased = serializers.SerializerMethodField()

    condition = ProductConditionDetailSerializer(read_only=True)
    discount_percent = serializers.SerializerMethodField()
    watching_count = serializers.SerializerMethodField()
    brand = BrandListSerializer(read_only=True)
    metadata = serializers.SerializerMethodField()
    watchlist_items = serializers.SerializerMethodField()

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
            "requires_shipping",
            "escrow_hold_period",
            "requires_inspection",
            "is_featured",
            "status",
            "brand",
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
            "breadcrumbs",
            "discount_percent",
            "watching_count",
            "authenticity_guaranteed",
            "warranty_period",
            "is_negotiable",
            "negotiation_deadline",
            "max_negotiation_rounds",
            "brand",
            "metadata",
            "watchlist_items",
            "total_views",
            "user_has_purchased",
        ]

    def get_seller(self, obj):
        profile_obj = obj.seller
        return UserShortSerializer(profile_obj, context=self.context).data

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
        # Use ProductVariantService to get real variants for this product
        variants = ProductVariantService.get_product_variants(obj.id, with_options=True)
        result = []
        for variant in variants:
            options = [
                {
                    "type": opt.variant_type.name,
                    "value": opt.value,
                    "slug": opt.slug,
                }
                for opt in variant.options.all()
            ]
            result.append(
                {
                    "id": variant.id,
                    "sku": variant.sku,
                    "price": str(variant.price) if variant.price is not None else None,
                    "stock_quantity": variant.total_inventory,
                    "available_quantity": variant.available_inventory,
                    "in_escrow_quantity": variant.in_escrow_inventory,
                    "is_active": variant.is_active,
                    "options": options,
                }
            )
        result.append(
            {
                "total_variants": len(variants),
            }
        )
        return result

    def get_details(self, obj):
        # Use ProductDetailService to get all details for this product
        details = ProductDetailService.get_product_details(obj.id)
        return ProductExtraDetailSerializer(details, many=True).data

    def get_breadcrumbs(self, obj):
        service = BreadcrumbService()
        breadcrumb_data = service.for_product(obj, include_brand=True)
        return BreadcrumbSerializer(breadcrumb_data, many=True).data

    def get_metadata(self, obj):
        meta = getattr(obj, "meta", None)
        if not meta:
            from apps.products.product_metadata.models import ProductMeta

            meta = ProductMeta.objects.filter(product=obj).first()
        if meta:
            return ProductMetaDetailSerializer(meta).data
        return None

    def get_watchlist_items(self, obj):
        request = self.context.get("request", None)
        if not request or not request.user.is_authenticated:
            return []
        from apps.products.product_watchlist.models import ProductWatchlistItem

        items = ProductWatchlistItem.objects.filter(product=obj, user=request.user)
        return ProductWatchlistItemListSerializer(
            items, many=True, context=self.context
        ).data

    def get_brand_detail(self, obj):
        brand = BrandService.get_brand_detail(obj.brand_id)

        return brand if brand else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Convert condition object to string
        data["condition"] = instance.condition.name
        return data

    def get_ratings(self, obj):
        """Get ratings from annotated fields"""
        return {
            "average": getattr(obj, "avg_rating_db", 0),
            "total": getattr(obj, "ratings_count_db", 0),
            "verified_count": getattr(obj, "verified_ratings_count", 0),
            # "reviews": getattr(obj, "user_rating", []),
            "distribution": {
                "5": getattr(obj, "five_star_count", 0),
                "4": getattr(obj, "four_star_count", 0),
                "3": getattr(obj, "three_star_count", 0),
                "2": getattr(obj, "two_star_count", 0),
                "1": getattr(obj, "one_star_count", 0),
            },
        }

    def get_user_has_purchased(self, obj):
        """Return purchase status for authenticated users"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return getattr(obj, "user_has_purchased", 0) > 0
        return None


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

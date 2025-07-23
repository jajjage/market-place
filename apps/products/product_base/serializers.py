from decimal import Decimal
from django.conf import settings
from rest_framework import serializers
from django.utils.text import slugify
from apps.categories.models import Category
from apps.categories.api.serializers import (
    CategorySummarySerializer,
)
from apps.core.serializers import (
    TimestampedModelSerializer,
    UserShortSerializer,
)

from apps.products.product_base.utils.seo_serializer_helper import get_structured_data
from apps.products.product_base.utils.utils import (
    clean_description,
    generate_enhanced_keywords,
    generate_meta_description,
    generate_seo_title,
    safe_get_variant_options,
)
from apps.products.product_brand.models import Brand
from apps.products.product_condition.models import ProductCondition
from apps.products.product_image.serializers import ProductImageSerializer
from .models import Product

from apps.products.product_condition.serializers import ProductConditionDetailSerializer
# from apps.products.product_image.serializers import ProductImageSerializer

from apps.products.product_variant.serializers import ProductVariantSerializer
from apps.products.product_brand.serializers import (
    BrandDetailSerializer,
    BrandListSerializer,
)
from apps.products.product_watchlist.serializers import (
    ProductWatchlistItemListSerializer,
)
# from apps.products.product_metadata.serializers import ProductMetaDetailSerializer
from apps.products.product_detail.serializers import (
    ProductExtraDetailSerializer,
)
import logging

logger = logging.getLogger(__name__)


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


class ProductListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer that works with prefetched data to prevent N+1 queries.
    """

    # Direct field access to prevent additional queries
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    condition_name = serializers.CharField(source="condition.name", read_only=True)

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

    # Use method fields for computed data that depends on relationships
    image_url = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    ratings = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "price",
            "description",
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
            "discount_percent",
            "brand_name",
            "image_url",
        ]

    def get_description(self, obj):
        """
        Use the clean_description utility to format the description.
        This avoids additional queries and uses pre-fetched data.
        """
        return clean_description(obj.description)

    def get_image_url(self, obj):
        """
        Use prefetched images to avoid additional queries.
        Uses the custom to_attr names from prefetch.
        """
        request = self.context.get("request")
        if hasattr(obj, "cached_primary_images") and obj.cached_primary_images:
            return (
                request.build_absolute_uri(obj.cached_primary_images[0].image_url)
                if request and obj.cached_primary_images[0].image_url
                else None
            )
        elif hasattr(obj, "cached_all_images") and obj.cached_all_images:
            return (
                obj.cached_all_images[0].image_url
                if obj.cached_all_images[0].image_url
                else None
            )
        return None

    def get_discount_percent(self, obj):
        """Calculate discount using prefetched data."""
        if obj.original_price and obj.price < obj.original_price:
            return round(
                ((obj.original_price - obj.price) / obj.original_price) * 100, 1
            )
        return 0

    def get_ratings(self, obj):
        """
        Use annotated fields to avoid queries.
        Falls back to prefetched data if needed.
        """
        return {
            "average": float(obj.avg_rating_db) if obj.avg_rating_db else 0.0,
            "count": obj.ratings_count_db or 0,
            "verified_count": obj.verified_ratings_count or 0,
        }

    def get_seller(self, obj):
        """
        Use prefetched seller data to avoid additional queries.
        """
        if obj.seller:
            return {
                "id": obj.seller.id,
                "name": f"{obj.seller.first_name} {obj.seller.last_name}".strip()
                or obj.seller.email,
                "email": obj.seller.email,
                "avatar_url": (
                    obj.seller.profile.avatar_url
                    if obj.seller.profile and obj.seller.profile.avatar_url
                    else None
                ),
            }
        return None


class ProductDetailSerializer(TimestampedModelSerializer):
    """
    Detailed serializer for a single product.
    Includes all information including nested category and seller details.
    """

    # brand_detail = serializers.SerializerMethodField(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    # variant_summary = serializers.SerializerMethodField()

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
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        write_only=True,
        required=False,
        help_text="Base price for auto-generated variants",
    )

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
    media = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    # Use direct annotation fields for ratings
    ratings = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()
    details = serializers.SerializerMethodField()
    category = CategorySummarySerializer(read_only=True)
    total_views = serializers.IntegerField(
        source="meta.views_count",
        max_value=1000,  # Use int for integer fields
        min_value=1,
        read_only=True,
    )
    user_has_purchased = serializers.SerializerMethodField()

    condition = ProductConditionDetailSerializer(read_only=True)
    discount_percent = serializers.SerializerMethodField()
    watching_count = serializers.SerializerMethodField()
    brand = BrandListSerializer(read_only=True)
    seo = serializers.SerializerMethodField()
    watchlist_items = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Product
        ref_name = "BaseProductDetail"
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
            "media",
            "escrowFee",
            "location",
            "description",
            "variants",
            # "variant_summary",
            "variant_combinations",
            "auto_generate_variants",
            "base_variant_price",
            "ratings",
            "details",
            # "breadcrumbs",
            "discount_percent",
            "watching_count",
            "authenticity_guaranteed",
            "warranty_period",
            "is_negotiable",
            "negotiation_deadline",
            "max_negotiation_rounds",
            "brand",
            # "metadata",
            "seo",
            "watchlist_items",
            "total_views",
            "user_has_purchased",
        ]
        read_only_fields = ("seo",)

    def get_description(self, obj):
        """
        Use the clean_description utility to format the description.
        This avoids additional queries and uses pre-fetched data.
        """
        return clean_description(obj.description)

    def get_seller(self, obj) -> dict | None:
        profile_obj = obj.seller
        return UserShortSerializer(profile_obj, context=self.context).data

    def get_seo(self, obj) -> dict:
        """
        Generate all SEO data in one place, using the fully prefetched 'obj'.
        Cache computations to avoid repeated processing.
        """
        base_url = settings.FRONTEND_BASE_URL

        # Cache the variant options computation since it's used multiple times
        if not hasattr(obj, "_cached_variant_options"):
            obj._cached_variant_options = {}
            variants = getattr(obj, "prefetched_variants", [])
            for variant in variants:
                obj._cached_variant_options[variant.id] = safe_get_variant_options(
                    variant
                )

        # Generate SEO data
        title = generate_seo_title(obj)
        meta_desc = generate_meta_description(obj)
        keywords = generate_enhanced_keywords(obj)
        structured_data = get_structured_data(obj)

        return {
            "title": title,
            "meta_description": meta_desc,
            "canonical_url": f"{base_url}/products/{obj.slug}",
            "keywords": keywords,
            "structured_data": structured_data,
            "open_graph": {
                "title": title,
                "description": meta_desc,
                # "image": get_first_image(obj),
                "url": f"{base_url}/products/{obj.slug}",
                "type": "product",
            },
        }

    def get_discount_percent(self, obj) -> float:
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

    def get_watching_count(self, obj) -> int:
        """Get the number of users watching this product from the annotation."""
        # This now reads the value that was calculated in the initial query.
        return getattr(obj, "watchers_count", 0)

    def get_watchlist_items(self, obj) -> list[dict]:
        items = getattr(obj, "prefetched_watchlist", [])
        return ProductWatchlistItemListSerializer(
            items, many=True, context=self.context
        ).data

    def get_brand_detail(self, obj) -> dict | None:
        brand = getattr(obj, "brand", None)
        return (
            BrandDetailSerializer(brand, context=self.context).data if brand else None
        )

    def get_details(self, obj) -> list[dict]:
        details = getattr(obj, "prefetched_details", [])
        logger.info(f"detail: {details}")
        return ProductExtraDetailSerializer(
            details, many=True, context=self.context
        ).data

    def get_media(self, obj) -> list[dict]:
        """
        Use prefetched images to avoid additional queries.
        Uses the custom to_attr names from prefetch.
        """
        if hasattr(obj, "prefetched_images") and obj.prefetched_images:
            return {
                "images": ProductImageSerializer(
                    obj.prefetched_images, many=True, context=self.context
                ).data,
                "videos": [],  # Assuming no video support yet
            }
        return {
            "images": [],
            "videos": [],
        }

    def get_variants(self, obj) -> list[dict]:
        variants = getattr(obj, "prefetched_variants", [])
        logger.info(f"variants: {variants}")
        out = []
        for v in variants:
            opts = [
                {"type": o.variant_type.name, "value": o.value, "slug": o.slug}
                for o in getattr(v, "prefetched_variant_options", [])
            ]
            imgs = [i.image_url for i in getattr(v, "prefetched_variant_images", [])]
            out.append(
                {
                    "id": v.id,
                    "sku": v.sku,
                    "price": str(v.price) if v.price is not None else None,
                    "stock_quantity": v.total_inventory,
                    "available_quantity": v.available_inventory,
                    "in_escrow_quantity": v.in_escrow_inventory,
                    "is_active": v.is_active,
                    "options": opts,
                    "images": imgs,
                }
            )
        out.append({"total_variants": len(variants)})
        return out

    def get_ratings(self, obj) -> dict:
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

    def get_user_has_purchased(self, obj) -> bool | None:
        """Return purchase status for authenticated users"""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return getattr(obj, "user_has_purchased", 0) > 0
        return None

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

    seller_id = serializers.UUIDField(source="seller.id")
    seller_name = serializers.CharField(source="seller.get_full_name")
    category_id = serializers.UUIDField(source="category.id")
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
            "watching_count",
            "images_count",
            "has_discount",
            "discount_amount",
            "discount_percent",
            "created_at",
            "updated_at",
        ]

    def get_watching_count(self, obj) -> int:
        return obj.watchers.count()

    def get_images_count(self, obj) -> int:
        return obj.images.count()

    def get_has_discount(self, obj) -> bool:
        return bool(obj.original_price and obj.price < obj.original_price)

    def get_discount_amount(self, obj) -> float:
        if obj.original_price and obj.price < obj.original_price:
            return obj.original_price - obj.price
        return 0

    def get_discount_percent(self, obj) -> float:
        if obj.original_price and obj.price < obj.original_price:
            discount = ((obj.original_price - obj.price) / obj.original_price) * 100
            return round(discount, 1)
        return 0

    def get_variants(self, obj) -> list[dict]:
        # This would need to be implemented based on your variant logic
        # For now, returning a sample structure
        return [
            {"type": "Color", "options": ["Brown", "Black", "Tan"]},
            {"type": "Condition", "options": ["New with tags", "Like New", "Good"]},
        ]

    def get_details(self, obj) -> list[dict]:
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

    def get_breadcrumbs(self, obj) -> list[dict]:
        # You can implement this based on your category structure
        return [
            {"name": "TrustLock", "href": "/"},
            {"name": "Fashion & Accessories", "href": "/explore?category=fashion"},
            {"name": "Women's Bags & Handbags", "href": "/explore?category=bags"},
        ]

    def to_representation(self, instance) -> dict:
        data = super().to_representation(instance)
        # Convert condition object to string
        data["condition"] = instance.condition.name
        return data


class ManageMetadataSerializer(TimestampedModelSerializer):
    """
    Serializer for managing product metadata.
    Used in the product management interface.
    """

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "price",
            "original_price",
            "currency",
            "category",
            "condition",
            "is_active",
            "is_featured",
            "status",
            "brand",
            "escrow_fee",
            "requires_inspection",
            "authenticity_guaranteed",
            "warranty_period",
        ]
        read_only_fields = ["id", "slug", "short_code"]

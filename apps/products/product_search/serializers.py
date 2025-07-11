from rest_framework import serializers
from apps.products.product_base.models import Product
from apps.products.product_search.utils.facet_raw import _get_buckets, _get_count
import logging

logger = logging.getLogger(__name__)


class ProductSearchSerializer(serializers.Serializer):
    """
    Serializer for ProductDocument search results
    Handles Elasticsearch response data with flexible field selection
    """

    # Basic product information
    title = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    short_code = serializers.CharField(read_only=True)

    # Seller information
    seller_id = serializers.IntegerField(read_only=True)
    seller_username = serializers.CharField(read_only=True)

    # Pricing information
    price = serializers.FloatField(read_only=True)
    original_price = serializers.FloatField(read_only=True, allow_null=True)
    currency = serializers.CharField(read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True, allow_null=True)

    # Category and brand
    category_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    category_slug = serializers.CharField(read_only=True)
    brand_id = serializers.IntegerField(read_only=True, allow_null=True)
    brand_name = serializers.CharField(read_only=True, allow_null=True)

    # Product condition
    condition_name = serializers.CharField(read_only=True)

    # Location
    location = serializers.CharField(read_only=True)

    # Status and boolean fields
    status = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_featured = serializers.BooleanField(read_only=True)
    is_negotiable = serializers.BooleanField(read_only=True)
    authenticity_guaranteed = serializers.BooleanField(read_only=True)
    requires_shipping = serializers.BooleanField(read_only=True)

    # Product specifications
    warranty_period = serializers.CharField(read_only=True, allow_null=True)

    # Ratings and reviews
    average_rating = serializers.FloatField(read_only=True, allow_null=True)
    rating_count = serializers.IntegerField(read_only=True)

    # Metadata
    views_count = serializers.IntegerField(read_only=True)
    seo_keywords = serializers.CharField(read_only=True, allow_null=True)

    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    # Popularity score
    popularity_score = serializers.FloatField(read_only=True, allow_null=True)

    # Elasticsearch metadata
    score = serializers.FloatField(read_only=True, allow_null=True)

    def to_representation(self, instance):
        """
        Custom representation handling for Elasticsearch Hit objects
        """
        # Handle both Elasticsearch Hit objects and regular dictionaries
        if hasattr(instance, "to_dict"):
            data = instance.to_dict()
            # Add Elasticsearch score if available
            if hasattr(instance.meta, "score"):
                data["score"] = instance.meta.score
        else:
            data = instance

        # Call parent to_representation with the processed data
        return super().to_representation(data)

    def get_formatted_price(self, obj):
        """
        Helper method to format price with currency
        """
        price = obj.get("price", 0)
        currency = obj.get("currency", "USD")
        return f"{currency} {price:.2f}"

    def get_discount_amount(self, obj):
        """
        Calculate discount amount if original price exists
        """
        original_price = obj.get("original_price")
        current_price = obj.get("price", 0)

        if original_price and original_price > current_price:
            return original_price - current_price
        return 0


class ProductSearchListSerializer(serializers.Serializer):
    """
    Lightweight serializer for product search list views
    Contains only essential fields for better performance
    """

    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    short_code = serializers.CharField(read_only=True)
    price = serializers.FloatField(read_only=True)
    currency = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    brand_name = serializers.CharField(read_only=True, allow_null=True)
    condition_name = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)
    is_featured = serializers.BooleanField(read_only=True)
    average_rating = serializers.FloatField(read_only=True, allow_null=True)
    rating_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    score = serializers.FloatField(read_only=True, allow_null=True)

    def to_representation(self, instance):
        """
        Custom representation for lightweight search results
        """
        if hasattr(instance, "to_dict"):
            data = instance.to_dict()
            if hasattr(instance.meta, "score"):
                data["score"] = instance.meta.score
        else:
            data = instance

        return super().to_representation(data)


class ProductSearchDetailSerializer(ProductSearchSerializer):
    """
    Extended serializer for detailed product search results
    Includes all fields and additional computed properties
    """

    # Additional computed fields
    formatted_price = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    rating_display = serializers.SerializerMethodField()

    def get_formatted_price(self, obj):
        """Format price with currency symbol"""
        return self.get_formatted_price(obj)

    def get_discount_amount(self, obj):
        """Calculate discount amount"""
        return self.get_discount_amount(obj)

    def get_has_discount(self, obj):
        """Check if product has discount"""
        return self.get_discount_amount(obj) > 0

    def get_rating_display(self, obj):
        """Format rating for display"""
        rating = obj.get("average_rating")
        count = obj.get("rating_count", 0)

        if rating:
            return f"{rating:.1f} ({count} reviews)"
        return "No reviews yet"


class ProductSearchSuggestionSerializer(serializers.Serializer):
    """
    Serializer for search suggestions and autocomplete
    """

    title = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    brand_name = serializers.CharField(read_only=True, allow_null=True)
    price = serializers.FloatField(read_only=True)
    currency = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        """
        Custom representation for suggestions
        """
        if hasattr(instance, "to_dict"):
            data = instance.to_dict()
        else:
            data = instance

        return super().to_representation(data)


class ProductSearchFacetSerializer(serializers.Serializer):
    """
    Serializer for search facets/aggregations
    """

    categories = serializers.DictField(read_only=True)
    brands = serializers.DictField(read_only=True)
    price_ranges = serializers.DictField(read_only=True)
    conditions = serializers.DictField(read_only=True)
    locations = serializers.DictField(read_only=True)

    def to_representation(self, instance):
        """
        Process aggregation data from Elasticsearch
        """
        logger.debug("Raw facet instance: %r", instance)
        if not instance:
            return {}

        result = {}
        # inside your serializer.to_representation()

        if "categories" in instance:
            buckets = _get_buckets(instance["categories"])
            result["categories"] = [
                {"key": b.get("key"), "count": _get_count(b)} for b in buckets
            ]

        # Brands
        if "brands" in instance:
            buckets = _get_buckets(instance["brands"])
            result["brands"] = [
                {"key": b.get("key"), "count": _get_count(b)} for b in buckets
            ]

        # Conditions
        if "conditions" in instance:
            buckets = _get_buckets(instance["conditions"])
            result["conditions"] = [
                {"key": b.get("key"), "count": _get_count(b)} for b in buckets
            ]

        # Locations
        if "locations" in instance:
            buckets = _get_buckets(instance["locations"])
            result["locations"] = [
                {"key": b.get("key"), "count": _get_count(b)} for b in buckets
            ]

        # Price Ranges
        if "price_ranges" in instance:
            buckets = _get_buckets(instance["price_ranges"])
            result["price_ranges"] = [
                {
                    "key": b.get("key"),
                    "count": _get_count(b),
                    "from": b.get("from"),
                    "to": b.get("to"),
                }
                for b in buckets
            ]

        # Ratings
        if "ratings" in instance:
            buckets = _get_buckets(instance["ratings"])
            result["ratings"] = [
                {"key": b.get("key"), "count": _get_count(b)} for b in buckets
            ]

        return result


class ProductSearchResponseSerializer(serializers.Serializer):
    """
    Complete search response serializer including results, facets, and metadata
    """

    results = ProductSearchListSerializer(many=True, read_only=True)
    facets = ProductSearchFacetSerializer(read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    total_pages = serializers.IntegerField(read_only=True)
    has_next = serializers.BooleanField(read_only=True)
    has_previous = serializers.BooleanField(read_only=True)
    query = serializers.CharField(read_only=True)
    took = serializers.IntegerField(read_only=True)  # Elasticsearch query time

    def to_representation(self, instance):
        """
        Process complete search response
        """
        data = super().to_representation(instance)

        # Add computed pagination fields
        if "total_count" in data and "page_size" in data:
            total_pages = (data["total_count"] + data["page_size"] - 1) // data[
                "page_size"
            ]
            data["total_pages"] = total_pages

            current_page = data.get("page", 1)
            data["has_next"] = current_page < total_pages
            data["has_previous"] = current_page > 1

        return data


class ProductSearchSerializer(serializers.ModelSerializer):
    """Serializer for product search results"""

    brand_name = serializers.CharField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    condition_name = serializers.CharField(read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)
    popularity_score = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "description",
            "slug",
            "short_code",
            "price",
            "original_price",
            "currency",
            "location",
            "is_active",
            "is_featured",
            "is_negotiable",
            "authenticity_guaranteed",
            "requires_shipping",
            "warranty_period",
            "created_at",
            "updated_at",
            "brand_name",
            "category_name",
            "condition_name",
            "discount_percentage",
            "average_rating",
            "rating_count",
            "views_count",
            "popularity_score",
        ]

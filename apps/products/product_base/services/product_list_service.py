from django.db.models import Avg, Count, Q, F, Prefetch

# from django.contrib.auth import get_user_model
from django.core.cache import cache
import logging
import hashlib
import json


from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.core.utils.cache_manager import CacheManager

# from apps.products.product_breadcrumb.models import Breadcrumb

from apps.products.product_base.utils.cache_service import ProductCacheVersionManager
from apps.products.product_image.models import ProductImage
from apps.products.product_rating.models import ProductRating

logger = logging.getLogger(__name__)


class ProductListService:
    CACHE_TTL = 60 * 15  # 15 minutes cache TTL
    LIST_KEYS_SET = "'safetrade:product_base:list:keys"
    CATEGORY_CACHE_MAPPING = "product_cache_categories"  # Maps cache keys to categories

    # @classmethod
    # def get_cached_product_list(cls, viewset, base_queryset):
    #     """
    #     Updated method that integrates with your existing ViewSet structure.
    #     Returns either cached data or a QuerySet depending on the action.
    #     """
    #     if viewset.action != "list":
    #         return cls.get_product_queryset(base_queryset)

    #     # Generate cache key with category tracking
    #     cache_key, involved_categories = cls._generate_list_cache_key_with_categories(
    #         viewset.request
    #     )
    #     logger.info(f"cache key: {cache_key}")
    #     # # Try to get cached serialized data
    #     cached_data = cache.get(cache_key)
    #     if cached_data:
    #         logger.info(f"Cache HIT for product list: {cache_key}")
    #         # For list action, we'll handle this in the viewset's list() method
    #         # Store cached data in viewset for later use
    #         viewset._cached_data = cached_data
    #         viewset._using_cached_data = True
    #         # Return a dummy queryset that won't be used
    #         return base_queryset.none()

    #     logger.info(f"Cache MISS for product list: {cache_key}")

    #     # Store cache info for later use after serialization
    #     viewset._cache_key = cache_key
    #     viewset._involved_categories = involved_categories
    #     viewset._using_cached_data = False

    #     # Return optimized queryset
    #     return cls.get_optimized_product_queryset(base_queryset)

    @staticmethod
    def generate_cache_key(request):
        """
        Generate cache key incorporating the current version.
        When version changes, all old cache keys become inaccessible.
        """
        # Get current cache version
        version = ProductCacheVersionManager.get_current_version()

        # Get all query parameters that affect the list
        params = {
            "page": request.GET.get("page", "1"),
            "page_size": request.GET.get("page_size", ""),
            "search": request.GET.get("search", ""),
            "ordering": request.GET.get("ordering", ""),
        }

        filter_params = [
            "category",
            "brand",
            "condition",
            "seller",
            "price_min",
            "price_max",
            "is_active",
            "created_at_after",
            "created_at_before",
            "inventory_min",
        ]

        for param in filter_params:
            if request.GET.get(param):
                params[param] = request.GET.get(param)

        # Create hash from parameters
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

        # Include version in the cache key
        cache_key = f"safetrade:product_list:v{version}:{params_hash}"

        logger.debug(f"Generated cache key: {cache_key}")
        return cache_key

    @classmethod
    def get_cached_list(cls, request, cache_timeout=300):
        """
        Get cached product list or return None if not found.
        """
        cache_key = cls.generate_cache_key(request)
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.info(f"Cache HIT for key: {cache_key}")
            return cached_data

        logger.info(f"Cache MISS for key: {cache_key}")
        return None

    @classmethod
    def set_cached_list(cls, request, data, cache_timeout=300):
        """
        Cache the product list data.
        """
        cache_key = cls.generate_cache_key(request)
        cache.set(cache_key, data, cache_timeout)
        logger.info(f"Cached data with key: {cache_key}")

    @staticmethod
    def get_optimized_product_queryset(queryset):
        """
        Your existing get_product_queryset method - enhanced for caching.
        This now ONLY handles QuerySet optimization, no caching logic.
        """
        # Select related for direct foreign keys
        base_queryset = queryset.select_related(
            "brand",
            "category",
            "condition",
            "seller",
            "seller__profile",
            "meta",
        ).only(
            # Product fields
            "id",
            "title",
            "price",
            "original_price",
            "currency",
            "slug",
            "short_code",
            "is_active",
            "is_featured",
            "status",
            "description",
            "location",
            "escrow_fee",
            "requires_inspection",
            # Related model fields (to prevent additional queries)
            "brand__id",
            "brand__name",
            "category__id",
            "category__name",
            "condition__id",
            "condition__name",
            "seller__id",
            "seller__first_name",
            "seller__last_name",
            "seller__email",
            "seller__profile__id",
            "seller__profile__avatar_url",
            "meta__id",
            "meta__views_count",
        )

        # Optimized prefetches with custom to_attr names
        primary_images_prefetch = Prefetch(
            "images",
            queryset=ProductImage.objects.filter(is_active=True, is_primary=True).only(
                "id", "product_id", "image_url", "is_primary", "display_order"
            ),
            to_attr="cached_primary_images",
        )

        all_images_prefetch = Prefetch(
            "images",
            queryset=ProductImage.objects.filter(is_active=True)
            .only("id", "product_id", "image_url", "is_primary", "display_order")
            .order_by("display_order"),
            to_attr="cached_all_images",
        )

        ratings_prefetch = Prefetch(
            "ratings",
            queryset=ProductRating.objects.filter(is_approved=True)
            .select_related("user")
            .only("id", "rating", "user_id", "is_verified_purchase", "is_approved"),
            to_attr="cached_ratings",
        )

        return base_queryset.prefetch_related(
            primary_images_prefetch,
            all_images_prefetch,
            ratings_prefetch,
            "variants",  # Add if needed
        ).annotate(
            avg_rating_db=Avg("ratings__rating", filter=Q(ratings__is_approved=True)),
            ratings_count_db=Count("ratings", filter=Q(ratings__is_approved=True)),
            verified_ratings_count=Count(
                "ratings",
                filter=Q(ratings__is_approved=True, ratings__is_verified_purchase=True),
            ),
            watchers_count=Count("watchers", distinct=True),
            total_views=F("meta__views_count"),
        )

    @classmethod
    def cache_serialized_data(cls, viewset, serialized_data):
        """
        Cache the serialized data after it's been created.
        Call this from the viewset after serialization.
        """
        if hasattr(viewset, "_cache_key") and not viewset._using_cached_data:
            try:
                cache.set(viewset._cache_key, serialized_data, cls.CACHE_TTL)
                logger.info(
                    f"Cached serialized product data: {len(serialized_data)} items"
                )
            except Exception as e:
                logger.warning(f"Failed to cache product list: {str(e)}")

    @staticmethod
    def _apply_viewset_filters(viewset, queryset):
        """
        Apply the same filters that the viewset would apply.
        This ensures consistency between cached and non-cached results.

        Args:
            viewset: ModelViewSet instance
            queryset: Base queryset

        Returns:
            Filtered queryset
        """
        # Apply the filterset (ProductFilter)
        if hasattr(viewset, "filterset_class") and viewset.filterset_class:
            filterset = viewset.filterset_class(viewset.request.GET, queryset=queryset)
            if filterset.is_valid():
                queryset = filterset.qs

        # Apply search
        search_query = viewset.request.GET.get("search")
        if search_query and hasattr(viewset, "search_fields"):
            search_conditions = Q()
            for field in viewset.search_fields:
                search_conditions |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(search_conditions)

        # Apply ordering
        ordering = viewset.request.GET.get("ordering")
        if ordering:
            # Validate ordering field against allowed fields
            if hasattr(viewset, "ordering_fields"):
                ordering_field = ordering.lstrip("-")
                if ordering_field in viewset.ordering_fields:
                    queryset = queryset.order_by(ordering)
        elif hasattr(viewset, "ordering") and viewset.ordering:
            queryset = queryset.order_by(*viewset.ordering)

        return queryset

    @staticmethod
    def get_cached_product_detail(viewset, instance):
        """
        Get cached product detail for retrieve action.

        Args:
            viewset: ModelViewSet instance
            instance: Product instance

        Returns:
            Cached or fresh product data
        """
        if viewset.action != "retrieve":
            return instance

        cache_key = CacheKeyManager.make_key(
            "product_base", "detail_by_shortcode", short_code=instance.short_code
        )

        # Check if cache exists
        if CacheManager.cache_exists(
            "product_base", "detail_by_shortcode", short_code=instance.short_code
        ):
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.info(f"Cache HIT for product detail: {cache_key}")
                return cached_data

        logger.info(f"Cache MISS for product detail: {cache_key}")

        # Get fresh data with optimizations
        optimized_instance = ProductListService.get_product_queryset(
            type(instance).objects.filter(pk=instance.pk)
        ).first()

        # Cache the instance (you might want to serialize it instead)
        cache.set(cache_key, optimized_instance, viewset.CACHE_TTL)
        logger.info(f"Cached product detail: {cache_key}")

        return optimized_instance

    @staticmethod
    def get_product_stats_cached():
        """
        Get cached product statistics.

        Returns:
            Dictionary with product statistics
        """
        cache_key = CacheKeyManager.make_key("product_base", "stats")

        cached_stats = cache.get(cache_key)
        if cached_stats:
            logger.info(f"Cache HIT for product stats: {cache_key}")
            return cached_stats

        logger.info(f"Cache MISS for product stats: {cache_key}")

        # Calculate fresh stats
        from apps.products.product_base.models import Product

        stats = {
            "total_products": Product.objects.count(),
            "active_products": Product.objects.filter(is_active=True).count(),
            "avg_price": Product.objects.aggregate(avg_price=Avg("price"))["avg_price"],
            "total_categories": Product.objects.values("category").distinct().count(),
            "total_brands": Product.objects.values("brand").distinct().count(),
        }

        # Cache for 30 minutes (STATS_CACHE_TTL)
        cache.set(cache_key, stats, 60 * 30)
        logger.info(f"Cached product stats: {cache_key}")

        return stats


class ProductCacheInvalidationService:
    """
    Simple invalidation service using version bumping.
    """

    @classmethod
    def invalidate_all_product_caches(cls):
        """
        Invalidate ALL product list caches instantly.
        This is now a single, atomic operation.
        """
        ProductCacheVersionManager.bump_version()
        logger.info("Invalidated all product list caches via version bump")

    @classmethod
    def invalidate_all_product_caches_async(cls):
        """
        Async version for high-traffic scenarios.
        """
        ProductCacheVersionManager.bump_version_async()
        logger.info("Invalidated all product list caches asynchronously")


class CacheUsageExamples:
    """
    Examples of how to use the enhanced cache system.
    """

    def create_catalog_key_example(self):
        """Example of creating your requested key type."""
        # Creates: product_catalog:all:page:1:sort:price_asc:v1
        key = CacheKeyManager.make_key(
            "product_catalog",
            "all_paginated",
            page=1,
            sort_criteria="price_asc",
            version="v1",
        )
        return key

    def cache_and_retrieve_example(self):
        """Example of caching and retrieving data."""
        key = self.create_catalog_key_example()

        # Cache data
        catalog_data = {"products": [], "total": 0, "page": 1}
        cache.set(key, catalog_data, timeout=3600)  # 1 hour

        # Retrieve data
        cached_data = cache.get(key)
        return cached_data

    def bulk_deletion_examples(self):
        """Examples of different deletion strategies."""

        # 1. Delete specific key
        CacheManager.invalidate_key(
            "product_catalog",
            "all_paginated",
            page=1,
            sort_criteria="price_asc",
            version="v1",
        )

        # 2. Delete all catalog pages (using pattern)
        CacheManager.invalidate_pattern("product_catalog", "all_pattern")

        # 3. Delete all caches for a resource
        CacheManager.invalidate("product_catalog")

        # 4. Delete category-specific caches
        CacheManager.invalidate_pattern(
            "product_catalog", "category_pattern", category_id=123
        )


class CacheDebugHelper:
    """Helper class for cache debugging and monitoring."""

    @staticmethod
    def list_all_keys_for_resource(resource_name):
        """List all cached keys for a resource."""
        return CacheManager.get_cache_stats(resource_name)

    @staticmethod
    def get_catalog_cache_info():
        """Get detailed info about catalog caches."""
        keys = CacheManager.get_cached_keys_by_pattern("product_catalog", "all_pattern")
        return {
            "total_keys": len(keys),
            "keys": keys[:10],  # First 10 keys for preview
            "sample_key": keys[0] if keys else None,
        }

    @staticmethod
    def verify_key_format(key_string):
        """Verify if a key matches expected format."""
        pattern = r"product_catalog:all:page:\d+:sort:\w+:v\w+"
        import re

        return bool(re.match(pattern, key_string))

from django.db.models import Avg, Count, Q
from django.core.cache import cache
import logging
import hashlib
import json
from django.utils import timezone

from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.core.utils.cache_manager import CacheManager

# from apps.products.product_breadcrumb.models import Breadcrumb
from django_redis import get_redis_connection

logger = logging.getLogger("products_performance")


class ProductListService:
    CACHE_TTL = 60 * 15  # 15 minutes cache TTL

    @staticmethod
    def get_cached_product_list(viewset, queryset):
        """
        Get cached product list for ModelViewSet.
        This method works with DRF's pagination and filtering.

        Args:
            viewset: The ModelViewSet instance
            queryset: Base queryset from get_queryset()

        Returns:
            Cached or optimized queryset
        """
        # Only cache for list action
        if viewset.action != "list":
            return ProductListService.get_product_queryset(queryset)

        # Generate cache key based on request parameters
        cache_key = ProductListService._generate_list_cache_key(viewset.request)
        logger.info(f"Generated cache key for product list: {cache_key}")
        # Check if we have cached data
        if cache.get(cache_key):
            logger.info(f"Cache HIT for product list: {cache_key}")
            # Return the cached queryset IDs and reconstruct
            cached_data = cache.get(cache_key)
            if cached_data and "product_ids" in cached_data:
                # Reconstruct queryset from cached IDs while preserving order
                preserved_order = {
                    pk: i for i, pk in enumerate(cached_data["product_ids"])
                }
                cached_queryset = ProductListService.get_product_queryset(
                    queryset
                ).filter(id__in=cached_data["product_ids"])
                # Maintain the original order
                return sorted(
                    cached_queryset, key=lambda x: preserved_order.get(x.id, 0)
                )

        logger.info(f"Cache MISS for product list: {cache_key}")

        # Get optimized queryset
        optimized_queryset = ProductListService.get_product_queryset(queryset)

        # Apply viewset's filtering, searching, and ordering
        filtered_queryset = ProductListService._apply_viewset_filters(
            viewset, optimized_queryset
        )

        # Cache the product IDs (not the full objects to save memory)
        try:
            # Limit the evaluation to avoid memory issues
            product_ids = list(filtered_queryset.values_list("id", flat=True)[:1000])
            cache_data = {
                "product_ids": product_ids,
                "timestamp": json.dumps(str(timezone.now()), default=str),
            }
            cache.set(cache_key, cache_data, ProductListService.CACHE_TTL)
            logger.info(
                f"Cached product list with {len(product_ids)} items: {cache_key}"
            )
        except Exception as e:
            logger.warning(f"Failed to cache product list: {str(e)}")

        return filtered_queryset

    @staticmethod
    def get_product_queryset(base_queryset):
        """
        Get optimized product queryset with related fields and annotations.
        This method is used to ensure efficient data retrieval for product details.

        Args:
            base_queryset: Base Product queryset

        Returns:
            Optimized queryset with select_related and prefetch_related
        """
        return (
            base_queryset.select_related("brand", "category", "condition", "seller")
            .prefetch_related(
                "images",
                "variants",
                "watchers",
                # Prefetch ratings for efficiency
                "ratings",
                # Prefetch breadcrumbs with their content_type
            )
            .annotate(
                # Add aggregated rating fields for efficiency
                avg_rating_db=Avg("ratings__rating"),
                ratings_count_db=Count("ratings"),
            )
        )

    @staticmethod
    def _generate_list_cache_key(request, version="v1"):
        """
        Generate cache key based on request parameters.
        Enhanced to support versioning and better structure.
        """
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

        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

        key = CacheKeyManager.make_key("product_base", "list", params=params_hash)
        return key

    @staticmethod
    def invalidate_product_list_caches():
        redis_conn = get_redis_connection("default")
        # django-redis strips KEY_PREFIX for you
        # cache.delete("safetrade:product_base:list:main")

        logger.info("Deleting list caches with pattern")
        keys = redis_conn.smembers("safetrade:product_base:list:keys")
        decoded_keys = [k.decode("utf-8") for k in keys]
        for key in decoded_keys:
            logger.info(f"Deleted single key: {key}")
            cache.delete(key)
            logger.info(f"✅ Deleted {key} list cache keys")

        else:
            logger.warning("⚠️ No product list cache keys found to delete")

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

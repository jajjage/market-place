import logging

from apps.core.throttle import BaseCacheThrottle

logger = logging.getLogger("products_performance")


class ProductListRateThrottle(BaseCacheThrottle):
    scope = "product_list"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductDetailRateThrottle(BaseCacheThrottle):
    scope = "product_detail"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductStatsRateThrottle(BaseCacheThrottle):
    scope = "product_stats"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductFeaturedRateThrottle(BaseCacheThrottle):
    scope = "product_featured"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductCreateRateThrottle(BaseCacheThrottle):
    scope = "product_create"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductUpdateRateThrottle(BaseCacheThrottle):
    scope = "product_update"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductDeleteRateThrottle(BaseCacheThrottle):
    scope = "product_delete"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductSearchRateThrottle(BaseCacheThrottle):
    scope = "product_search"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


# Example usage in DRF ViewSet:
# throttle_classes = [ProductListRateThrottle]

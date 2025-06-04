from apps.core.throttle import BaseCacheThrottle


class BrandSearchThrottle(BaseCacheThrottle):
    scope = "brand_search"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class BrandCreateThrottle(BaseCacheThrottle):
    scope = "brand_create"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"

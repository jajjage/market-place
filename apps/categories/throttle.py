from apps.core.throttle import BaseCacheThrottle


class CategoryRateThrottle(BaseCacheThrottle):
    """Custom throttle for category operations."""

    scope = "category"

    def get_cache_key(self, request, view):
        """Custom cache key for general category operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"

import logging

from apps.core.throttle import BaseCacheThrottle

logger = logging.getLogger(__name__)


class WatchlistRateThrottle(BaseCacheThrottle):
    """
    General watchlist operations throttle.
    Applied to: list, stats, check_product endpoints
    """

    scope = "watchlist"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class WatchlistCreateThrottle(BaseCacheThrottle):
    """
    Throttle for toggle operations (add/remove single product).
    Applied to: toggle_product endpoint
    """

    scope = "watchlist_toggle"

    def get_cache_key(self, request, view):
        """Custom cache key for toggle operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_toggle"

    def throttle_failure(self):
        """Custom failure handling for toggle operations."""
        logger.warning(
            f"Toggle throttle exceeded: user={getattr(self, 'user_id', 'unknown')}, "
            f"requests={len(self.history)}, limit={self.num_requests}"
        )
        return False


class WatchlistBulkThrottle(BaseCacheThrottle):
    """
    Strict throttle for bulk operations (add/remove multiple products).
    Applied to: bulk_operation endpoint
    """

    scope = "watchlist_bulk"

    def get_cache_key(self, request, view):
        """Custom cache key for bulk operations."""
        base_key = super().get_cache_key(request, view)

        # Include product count in cache key for more granular control
        product_count = 0
        if hasattr(request, "data") and isinstance(request.data, dict):
            product_ids = request.data.get("product_ids", [])
            product_count = len(product_ids) if isinstance(product_ids, list) else 0

        return f"{base_key}_bulk_{min(product_count, 50)}"  # Cap at 50 for cache efficiency

    def allow_request(self, request, view):
        """
        Custom logic for bulk operations with additional validation.
        """
        # Additional check for bulk operation size
        if hasattr(request, "data") and isinstance(request.data, dict):
            product_ids = request.data.get("product_ids", [])
            if isinstance(product_ids, list) and len(product_ids) > 100:
                logger.warning(
                    f"Bulk operation too large: {len(product_ids)} products, "
                    f"user={getattr(request.user, 'id', 'unknown')}"
                )
                return False

        return super().allow_request(request, view)

    def throttle_failure(self):
        """Custom failure handling for bulk operations."""
        logger.error(
            f"Bulk throttle exceeded: requests={len(self.history)}, "
            f"limit={self.num_requests}, window={self.duration}s"
        )
        return False


class AdminWatchlistThrottle(BaseCacheThrottle):
    """
    Separate throttle for admin/staff operations.
    Applied to: by_product endpoint (staff only)
    """

    scope = "watchlist_admin"

    def get_cache_key(self, request, view):
        """Custom cache key for admin operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_admin"

    def allow_request(self, request, view):
        """
        Only apply throttling to staff users.
        """
        if not request.user.is_authenticated or not request.user.is_staff:
            return True  # Let permission handling deal with non-staff users

        return super().allow_request(request, view)

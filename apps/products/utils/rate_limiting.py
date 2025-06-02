from django.core.cache import cache
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import Throttled
import time
import logging

logger = logging.getLogger(__name__)


class BaseCacheThrottle(UserRateThrottle):
    """
    Base cache-based throttle with custom cache key generation and logging.
    """

    def get_cache_key(self, request, view):
        """
        Generate cache key for throttling.
        Format: throttle_{scope}_{user_identifier}
        """
        if request.user.is_authenticated:
            user_identifier = str(request.user.id)
        else:
            # For anonymous users, use IP address
            user_identifier = request.META.get("REMOTE_ADDR", "unknown")

        return f"throttle_{self.scope}_{user_identifier}"

    def allow_request(self, request, view):
        """
        Check if request should be allowed based on cache history.
        """
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.now = time.time()
        self.history = cache.get(self.key, [])

        # Remove requests outside the time window
        while self.history and self.history[0] <= self.now - self.duration:
            self.history.pop(0)

        # Check if we've exceeded the rate limit
        if len(self.history) >= self.num_requests:
            # Log throttle event for monitoring
            logger.warning(
                f"Rate limit exceeded for {self.scope}: "
                f"key={self.key}, requests={len(self.history)}, "
                f"limit={self.num_requests}, window={self.duration}s"
            )
            return self.throttle_failure()

        return self.throttle_success()

    def throttle_success(self):
        """
        Called when request is allowed. Update cache with current request.
        """
        # Add current request timestamp
        self.history.append(self.now)

        # Store updated history with TTL equal to time window
        cache.set(self.key, self.history, timeout=int(self.duration) + 1)

        # Log successful request for debugging
        logger.debug(
            f"Request allowed for {self.scope}: "
            f"key={self.key}, count={len(self.history)}/{self.num_requests}"
        )

        return True

    def throttle_failure(self):
        """
        Called when request should be throttled.
        """
        return False

    def wait(self):
        """
        Return the number of seconds to wait before next request.
        """
        if not self.history:
            return None

        # Time until oldest request expires
        remaining_duration = self.duration - (self.now - self.history[0])
        return max(remaining_duration, 0)


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


class WatchlistToggleThrottle(BaseCacheThrottle):
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


# Custom throttle exception for better error messages
class WatchlistThrottled(Throttled):
    """Custom throttled exception with helpful messages."""

    def __init__(self, wait=None, detail=None, code=None, scope=None):
        if detail is None:
            if scope == "watchlist_toggle":
                detail = "Too many toggle requests. Please wait before adding/removing more products."
            elif scope == "watchlist_bulk":
                detail = "Too many bulk operations. Please wait before performing more bulk actions."
            elif scope == "watchlist":
                detail = "Too many watchlist requests. Please wait before making more requests."
            else:
                detail = "Request rate limit exceeded. Please wait before trying again."

        super().__init__(wait=wait, detail=detail, code=code)


# Utility function to get remaining quota
def get_throttle_status(request, throttle_class):
    """
    Get remaining quota for a specific throttle.
    Useful for API responses to show users their remaining requests.
    """
    throttle = throttle_class()
    throttle.allow_request(request, None)

    if hasattr(throttle, "history") and hasattr(throttle, "num_requests"):
        used = len(throttle.history)
        remaining = max(0, throttle.num_requests - used)
        reset_time = None

        if throttle.history:
            reset_time = throttle.history[0] + throttle.duration

        return {
            "used": used,
            "remaining": remaining,
            "limit": throttle.num_requests,
            "reset_time": reset_time,
            "window_seconds": throttle.duration,
        }

    return None


class RatingRateThrottle(BaseCacheThrottle):
    """
    General watchlist operations throttle.
    Applied to: list, stats, check_product endpoints
    """

    scope = "ratings_create"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class RatingVoteHelpfulThrottle(BaseCacheThrottle):
    """
    Throttle for toggle operations (add/remove single product).
    Applied to: toggle_product endpoint
    """

    scope = "vote_helpful"

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

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


# Custom throttle exception for better error messages
class ThrottledException(Throttled):
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

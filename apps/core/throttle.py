from django.core.cache import cache
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import Throttled
import time
import logging

logger = logging.getLogger(__name__)


class BaseCacheThrottle(UserRateThrottle):
    """
    Base cache‐based throttle. Subclasses only need to set `scope`.
    """

    def get_cache_key(self, request, view):
        """
        Generates a key like "throttle_{scope}_{user_id_or_ip}".
        """
        if request.user.is_authenticated:
            user_identifier = str(request.user.id)
        else:
            user_identifier = request.META.get("REMOTE_ADDR", "unknown")

        return f"throttle_{self.scope}_{user_identifier}"

    def allow_request(self, request, view):
        # If no rate is configured for this scope, skip throttling
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        self.now = time.time()
        self.history = cache.get(self.key, [])

        # Remove timestamps that are older than the window
        while self.history and self.history[0] <= self.now - self.duration:
            self.history.pop(0)

        if len(self.history) >= self.num_requests:
            logger.warning(
                f"Rate limit exceeded for {self.scope}: "
                f"key={self.key}, requests={len(self.history)}, "
                f"limit={self.num_requests}, window={self.duration}s"
            )
            return False  # Tell DRF to call its throttled logic

        return True  # Allowed

    def throttled(self, request, view):
        """
        DRF uses this hook to build the exception. We keep it simple:
        disable DRF’s Retry-After injection here, because we handle wait()
        in the global exception handler.
        """
        return super().throttled(request, view)

    def wait(self):
        """
        DRF calls this to get the remaining seconds before the next request
        is allowed. We compute "window - (now - oldest_request)".
        """
        if not hasattr(self, "history") or not self.history:
            return None
        remaining = self.duration - (self.now - self.history[0])
        return max(remaining, 0)

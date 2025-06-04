import logging
from apps.core.throttle import BaseCacheThrottle

logger = logging.getLogger(__name__)


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

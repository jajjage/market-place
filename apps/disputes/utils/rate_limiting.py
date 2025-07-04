from apps.core.throttle import BaseCacheThrottle


class DisputeRateThrottle(BaseCacheThrottle):
    """Custom throttle for dispute creation"""

    scope = "dispute_create"
    rate = "5/hour"  # Max 5 disputes per hour per user

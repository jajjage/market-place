from apps.core.throttle import BaseCacheThrottle


class RatingCreateThrottle(BaseCacheThrottle):
    """Limit rating creation to prevent spam"""

    scope = "rating_create"
    rate = "10/hour"  # Max 10 ratings per hour per user


class RatingViewThrottle(BaseCacheThrottle):
    """General throttling for rating views"""

    scope = "rating_view"
    rate = "100/hour"

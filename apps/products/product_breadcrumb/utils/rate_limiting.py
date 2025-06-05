from apps.core.throttle import BaseCacheThrottle


class BreadcrumbRateThrottle(BaseCacheThrottle):
    scope = "breadcrumb"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        # Append a suffix if you want to differentiate between, e.g.,
        # list vs. search endpoints. Here we just tack on "_general".
        return f"{base_key}_general"

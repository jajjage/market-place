from apps.core.throttle import BaseCacheThrottle


class NegotiationRateThrottle(BaseCacheThrottle):
    """Custom rate limiting for negotiations"""

    scope = "negotiation"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class NegotiationInitiateRateThrottle(BaseCacheThrottle):
    """Custom rate limiting for negotiations"""

    scope = "negotiation_initiate"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class NegotiationRespondRateThrottle(BaseCacheThrottle):
    """Custom rate limiting for negotiations"""

    scope = "negotiation_respond"

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}

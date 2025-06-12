from apps.core.throttle import BaseCacheThrottle


class EscrowTransactionListRateThrottle(BaseCacheThrottle):
    scope = "escrow_transaction_list"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_list"


class EscrowTransactionCreateRateThrottle(BaseCacheThrottle):
    scope = "escrow_transaction_create"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_create"


class EscrowTransactionUpdateRateThrottle(BaseCacheThrottle):
    scope = "escrow_transaction_update"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_update"


class EscrowTransactionTrackRateThrottle(BaseCacheThrottle):
    scope = "escrow_transaction_track"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_track"


class EscrowTransactionMyPurchaseRateThrottle(BaseCacheThrottle):
    scope = "my_purchases"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_track"


class EscrowTransactionMySaleRateThrottle(BaseCacheThrottle):
    scope = "my_sales"

    def get_cache_key(self, request, view):
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_track"

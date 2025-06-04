import logging
from apps.core.throttle import BaseCacheThrottle

logger = logging.getLogger(__name__)


class ProductDetailListThrottle(BaseCacheThrottle):
    """
    Throttle for list endpoint: 100 requests/minute per IP (GET)
    """

    scope = "product_detail_list"
    rate = "100/min"

    def get_cache_key(self, request, view):
        if request.method == "GET":
            ip = self.get_ident(request)
            return f"product_detail_list_{ip}"
        return None


class ProductDetailRetrieveThrottle(BaseCacheThrottle):
    """
    Throttle for retrieve endpoint: 100 requests/minute per IP (GET)
    """

    scope = "product_detail_retrieve"
    rate = "100/min"

    def get_cache_key(self, request, view):
        if request.method == "GET":
            ip = self.get_ident(request)
            return f"product_detail_retrieve_{ip}"
        return None


class ProductDetailWriteThrottle(BaseCacheThrottle):
    """
    Throttle for create/update/partial_update: 30 requests/minute per user (POST, PUT, PATCH)
    """

    scope = "product_detail_write"
    rate = "30/min"

    def get_cache_key(self, request, view):
        if request.method in ["POST", "PUT", "PATCH"]:
            user_id = getattr(request.user, "id", None)
            if user_id:
                return f"product_detail_write_{user_id}"
        return None

    def throttle_failure(self):
        logger.warning(
            f"Write throttle exceeded: user={getattr(self, 'user_id', 'unknown')}, "
            f"requests={len(self.history)}, limit={self.num_requests}"
        )
        return False

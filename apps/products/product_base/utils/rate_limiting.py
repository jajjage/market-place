import logging

from apps.core.throttle import BaseCacheThrottle

logger = logging.getLogger("products_performance")


class ProductListRateThrottle(BaseCacheThrottle):
    scope = "product_list"


class ProductDetailRateThrottle(BaseCacheThrottle):
    scope = "product_detail"


class ProductStatsRateThrottle(BaseCacheThrottle):
    scope = "product_stats"


class ProductFeaturedRateThrottle(BaseCacheThrottle):
    scope = "product_featured"


class ProductCreateRateThrottle(BaseCacheThrottle):
    scope = "product_create"


class ProductUpdateRateThrottle(BaseCacheThrottle):
    scope = "product_update"


class ProductDeleteRateThrottle(BaseCacheThrottle):
    scope = "product_delete"


# Example usage in DRF ViewSet:
# throttle_classes = [ProductListRateThrottle]

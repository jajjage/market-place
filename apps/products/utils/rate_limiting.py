from apps.core.throttle import BaseCacheThrottle
import logging

logger = logging.getLogger("products_performance")


class ProductListRateThrottle(BaseCacheThrottle):
    scope = "product_list"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductDetailRateThrottle(BaseCacheThrottle):
    scope = "product_detail"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductStatsRateThrottle(BaseCacheThrottle):
    scope = "product_stats"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductFeaturedRateThrottle(BaseCacheThrottle):
    scope = "product_featured"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductCreateRateThrottle(BaseCacheThrottle):
    scope = "product_create"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductUpdateRateThrottle(BaseCacheThrottle):
    scope = "product_update"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductDeleteRateThrottle(BaseCacheThrottle):
    scope = "product_delete"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class ProductSearchRateThrottle(BaseCacheThrottle):
    scope = "product_search"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


# Example usage in DRF ViewSet:
# throttle_classes = [ProductListRateThrottle]



class BrandSearchThrottle(BaseCacheThrottle):
    scope = "brand_search"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class BrandCreateThrottle(BaseCacheThrottle):
    scope = "brand_create"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"



class ProductConditionRateThrottle(BaseCacheThrottle):
    scope = "product_condition"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


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



logger = logging.getLogger(__name__)


class ImageUploadThrottle(BaseCacheThrottle):
    """
    Throttle for toggle operations (add/remove single product).
    Applied to: toggle_product endpoint
    """

    scope = "upload_image"

    def get_cache_key(self, request, view):
        """Custom cache key for upload image operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_upload"

    def throttle_failure(self):
        """Custom failure handling for upload image operations."""
        logger.warning(
            f"Toggle throttle exceeded: user={getattr(self, 'user_id', 'unknown')}, "
            f"requests={len(self.history)}, limit={self.num_requests}"
        )
        return False


class ImageBulkUploadThrottle(BaseCacheThrottle):
    """
    Strict throttle for bulk operations (add/remove multiple products).
    Applied to: bulk_operation endpoint
    """

    scope = "image_bulk_upload"

    def get_cache_key(self, request, view):
        """Custom cache key for bulk operations."""
        base_key = super().get_cache_key(request, view)

        # Include product count in cache key for more granular control
        product_count = 0
        if hasattr(request, "data") and isinstance(request.data, dict):
            product_ids = request.data.get("product_ids", [])
            product_count = len(product_ids) if isinstance(product_ids, list) else 0

        return f"{base_key}_bulk_{min(product_count, 50)}"  # Cap at 50 for cache efficiency

    def allow_request(self, request, view):
        """
        Custom logic for bulk operations with additional validation.
        """
        # Additional check for bulk operation size
        if hasattr(request, "data") and isinstance(request.data, dict):
            product_ids = request.data.get("product_ids", [])
            if isinstance(product_ids, list) and len(product_ids) > 100:
                logger.warning(
                    f"Bulk operation too large: {len(product_ids)} products, "
                    f"user={getattr(request.user, 'id', 'unknown')}"
                )
                return False

        return super().allow_request(request, view)

    def throttle_failure(self):
        """Custom failure handling for bulk operations."""
        logger.error(
            f"Bulk throttle exceeded: requests={len(self.history)}, "
            f"limit={self.num_requests}, window={self.duration}s"
        )
        return False





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




logger = logging.getLogger(__name__)


class WatchlistRateThrottle(BaseCacheThrottle):
    """
    General watchlist operations throttle.
    Applied to: list, stats, check_product endpoints
    """

    scope = "watchlist"

    def get_cache_key(self, request, view):
        """Custom cache key for general watchlist operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_general"


class WatchlistCreateThrottle(BaseCacheThrottle):
    """
    Throttle for toggle operations (add/remove single product).
    Applied to: toggle_product endpoint
    """

    scope = "watchlist_toggle"

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


class WatchlistBulkThrottle(BaseCacheThrottle):
    """
    Strict throttle for bulk operations (add/remove multiple products).
    Applied to: bulk_operation endpoint
    """

    scope = "watchlist_bulk"

    def get_cache_key(self, request, view):
        """Custom cache key for bulk operations."""
        base_key = super().get_cache_key(request, view)

        # Include product count in cache key for more granular control
        product_count = 0
        if hasattr(request, "data") and isinstance(request.data, dict):
            product_ids = request.data.get("product_ids", [])
            product_count = len(product_ids) if isinstance(product_ids, list) else 0

        return f"{base_key}_bulk_{min(product_count, 50)}"  # Cap at 50 for cache efficiency

    def allow_request(self, request, view):
        """
        Custom logic for bulk operations with additional validation.
        """
        # Additional check for bulk operation size
        if hasattr(request, "data") and isinstance(request.data, dict):
            product_ids = request.data.get("product_ids", [])
            if isinstance(product_ids, list) and len(product_ids) > 100:
                logger.warning(
                    f"Bulk operation too large: {len(product_ids)} products, "
                    f"user={getattr(request.user, 'id', 'unknown')}"
                )
                return False

        return super().allow_request(request, view)

    def throttle_failure(self):
        """Custom failure handling for bulk operations."""
        logger.error(
            f"Bulk throttle exceeded: requests={len(self.history)}, "
            f"limit={self.num_requests}, window={self.duration}s"
        )
        return False


class AdminWatchlistThrottle(BaseCacheThrottle):
    """
    Separate throttle for admin/staff operations.
    Applied to: by_product endpoint (staff only)
    """

    scope = "watchlist_admin"

    def get_cache_key(self, request, view):
        """Custom cache key for admin operations."""
        base_key = super().get_cache_key(request, view)
        return f"{base_key}_admin"

    def allow_request(self, request, view):
        """
        Only apply throttling to staff users.
        """
        if not request.user.is_authenticated or not request.user.is_staff:
            return True  # Let permission handling deal with non-staff users

        return super().allow_request(request, view)

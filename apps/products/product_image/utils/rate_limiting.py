import logging

from apps.core.throttle import BaseCacheThrottle

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

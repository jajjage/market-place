import time
from django.core.cache import cache
import logging


logger = logging.getLogger(__name__)


class ProductCacheVersionManager:
    """
    Manages cache versioning for product lists.
    Instead of tracking and deleting individual cache keys,
    we use a version-based approach for instant invalidation.
    """

    VERSION_KEY = "safetrade:product_list:version"
    VERSION_TTL = 86400 * 30  # 30 days

    @classmethod
    def get_current_version(cls):
        """
        Get the current cache version.
        If no version exists, create one.
        """
        version = cache.get(cls.VERSION_KEY)
        if version is None:
            version = int(time.time())
            cache.set(cls.VERSION_KEY, version, cls.VERSION_TTL)
            logger.info(f"Created new cache version: {version}")
        return version

    @classmethod
    def bump_version(cls):
        """
        Bump the cache version, effectively invalidating all product list caches.
        This is atomic and fast - just one cache write operation.
        """
        new_version = int(time.time())
        cache.set(cls.VERSION_KEY, new_version, cls.VERSION_TTL)
        logger.info(f"Bumped product cache version to: {new_version}")
        return new_version

    @classmethod
    def bump_version_async(cls):
        """
        Async version for high-traffic scenarios.
        """
        from apps.products.product_base.tasks import bump_product_cache_version

        bump_product_cache_version.delay()

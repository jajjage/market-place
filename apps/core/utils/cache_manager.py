import logging
from django.conf import settings
from django.core.cache import cache
from django_redis import get_redis_connection

from .cache_key_manager import CacheKeyManager

logger = logging.getLogger("monitoring")


class CacheManager:
    """
    Centralized invalidation of cache keys/patterns per resource,
    fully driven by settings.CACHE_KEY_TEMPLATES.
    """

    @staticmethod
    def invalidate(resource_name: str, **kwargs):
        """
        Invalidate all keys/patterns for the given resource.

        - For each template in CACHE_KEY_TEMPLATES[resource_name]:
            • If the template has NO '*', call make_key(...) and delete that one key.
            • If the template has a '*', call make_pattern(...) to get a wildcard, then
              scan Redis and delete all matching keys.

        Example:
            CacheManager.invalidate("brand", id=42)
        """
        templates = getattr(settings, "CACHE_KEY_TEMPLATES", {})
        if resource_name not in templates:
            logger.warning(f"No cache templates found for resource '{resource_name}'")
            return

        resource_templates = templates[resource_name]

        # 1) Exact keys (no wildcard) → delete_many
        to_delete = []
        for key_name, raw_template in resource_templates.items():
            # If raw_template has no '*', treat as exact:
            if "*" not in raw_template:
                try:
                    actual_key = CacheKeyManager.make_key(
                        resource_name, key_name, **kwargs
                    )
                    to_delete.append(actual_key)
                except Exception:
                    # Already logged inside make_key; skip
                    continue

        if to_delete:
            cache.delete_many(to_delete)

        # 2) Wildcard keys → redis.keys(...) + delete
        redis_conn = get_redis_connection("default")
        for key_name, raw_template in resource_templates.items():
            if "*" in raw_template:
                try:
                    pattern = CacheKeyManager.make_pattern(
                        resource_name, key_name, **kwargs
                    )
                except Exception:
                    # Already logged inside make_pattern; skip
                    continue

                keys = redis_conn.keys(pattern)
                if keys:
                    redis_conn.delete(*keys)

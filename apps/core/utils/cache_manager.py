import logging
from django.conf import settings
from django.core.cache import cache
from django_redis import get_redis_connection
from typing import List, Dict, Any

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

    @staticmethod
    def invalidate_key(resource_name: str, key_name: str, **kwargs):
        """
        Invalidate a specific cache key.

        Example:
            CacheManager.invalidate_key("brand", "detail", id=42)
            # Deletes only the "brand:detail:42" key
        """
        try:
            cache_key = CacheKeyManager.make_key(resource_name, key_name, **kwargs)
            cache.delete(cache_key)
            logger.debug(f"Invalidated cache key: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to invalidate key {resource_name}:{key_name} - {e}")

    @staticmethod
    def invalidate_pattern(resource_name: str, key_name: str, **kwargs):
        """
        Invalidate cache keys matching a specific pattern.

        Example:
            CacheManager.invalidate_pattern("brand", "variants_all", id=42)
            # Deletes all keys matching "brand:variants:42:*"
        """
        try:
            pattern = CacheKeyManager.make_pattern(resource_name, key_name, **kwargs)
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys(pattern)
            if keys:
                redis_conn.delete(*keys)
                logger.debug(
                    f"Invalidated {len(keys)} keys matching pattern: {pattern}"
                )
        except Exception as e:
            logger.error(
                f"Failed to invalidate pattern {resource_name}:{key_name} - {e}"
            )

    @staticmethod
    def get_cached_keys_by_pattern(
        resource_name: str, key_name: str, **kwargs
    ) -> List[str]:
        """
        Get all cache keys matching a pattern (useful for debugging/monitoring).

        Example:
            keys = CacheManager.get_cached_keys_by_pattern("brand", "variants_all", id=42)
            # Returns list of all keys matching "brand:variants:42:*"
        """
        try:
            pattern = CacheKeyManager.make_pattern(resource_name, key_name, **kwargs)
            print(f"Searching for keys with pattern: {pattern}")
            logger.debug(f"Searching for keys with pattern: {pattern}")
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys(pattern)
            print(f"Found keys: {keys}")
            logger.debug(f"Found keys: {keys}")
            return [
                key.decode("utf-8") if isinstance(key, bytes) else key for key in keys
            ]
        except Exception as e:
            logger.error(
                f"Failed to get keys for pattern {resource_name}:{key_name} - {e}"
            )
            return []

    @staticmethod
    def cache_exists(resource_name: str, key_name: str, **kwargs) -> bool:
        """
        Check if a specific cache key exists.

        Example:
            exists = CacheManager.cache_exists("brand", "detail", id=42)
        """
        try:
            cache_key = CacheKeyManager.make_key(resource_name, key_name, **kwargs)
            return cache.get(cache_key) is not None
        except Exception as e:
            logger.error(
                f"Failed to check cache existence for {resource_name}:{key_name} - {e}"
            )
            return False

    @staticmethod
    def get_cache_stats(resource_name: str) -> Dict[str, Any]:
        """
        Get statistics about cached keys for a resource (useful for monitoring).

        Returns dict with counts of cached keys per template.
        """
        templates = getattr(settings, "CACHE_KEY_TEMPLATES", {})
        if resource_name not in templates:
            return {}

        stats = {}
        redis_conn = get_redis_connection("default")

        for key_name, raw_template in templates[resource_name].items():
            if "*" in raw_template:
                # For wildcard patterns, we need to make a broad pattern to count
                try:
                    # Replace all {placeholders} with * for counting
                    count_pattern = raw_template
                    import re

                    count_pattern = re.sub(r"\{[^}]+\}", "*", count_pattern)

                    prefix = settings.CACHES["default"].get("KEY_PREFIX", "")
                    if prefix:
                        count_pattern = f"{prefix}:{count_pattern}"

                    keys = redis_conn.keys(count_pattern)
                    stats[key_name] = len(keys)
                except Exception:
                    stats[key_name] = 0
            else:
                # For exact keys, we can't count without specific parameters
                stats[key_name] = "exact_key_template"

        return stats

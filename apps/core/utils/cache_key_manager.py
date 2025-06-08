# apps/core/utils/cache_manager.py

import logging
from typing import Dict, List
from django.conf import settings

logger = logging.getLogger("monitoring")  # or create a new logger if desired


class CacheKeyManager:
    """
    Centralized creation of cache keys (and wildcard patterns) based on templates
    defined in settings.CACHE_KEY_TEMPLATES.

    Usage:
        from apps.core.utils.cache_manager import CacheKeyManager

        # Exact key (no wildcard):
        key = CacheKeyManager.make_key("brand", "detail", id=42)
        # → "myproject:brand:detail:42"

        # Wildcard pattern:
        pattern = CacheKeyManager.make_pattern("brand", "variants_all", id=42)
        # → "myproject:brand:variants:42:*"
    """

    @staticmethod
    def _get_template(resource_name: str, key_name: str) -> str:
        """Retrieve the raw template string, or log + raise if missing."""
        templates = getattr(settings, "CACHE_KEY_TEMPLATES", {})
        if resource_name not in templates:
            logger.error(
                f"[CacheKeyManager] No templates configured for resource '{resource_name}'"
            )
            raise KeyError(f"No templates for resource '{resource_name}'")
        resource_templates = templates[resource_name]
        if key_name not in resource_templates:
            logger.error(
                f"[CacheKeyManager] No template named '{key_name}' for resource '{resource_name}'"
            )
            raise KeyError(f"No key '{key_name}' for resource '{resource_name}'")
        return resource_templates[key_name]

    @staticmethod
    def make_key(resource_name: str, key_name: str, **kwargs) -> str:
        """
        Build an exact cache key (no '*').

        Example:
            CacheKeyManager.make_key("brand", "detail", id=42)
            → "myproject:brand:detail:42"
        """
        raw_template = CacheKeyManager._get_template(resource_name, key_name)
        try:
            filled = raw_template.format(**kwargs)
            logger.info(f"Generated cache key: {filled}")
        except KeyError as e:
            missing = e.args[0]
            logger.error(
                f"[CacheKeyManager] Missing argument '{missing}' when formatting '{raw_template}'"
            )
            raise

        # Prepend Django's key prefix (if any):
        prefix = settings.CACHES["default"].get("KEY_PREFIX", "")
        if prefix:
            return f"{prefix}:{filled}"
        return filled

    @staticmethod
    def make_pattern(resource_name: str, key_name: str, **kwargs) -> str:
        """
        Build a wildcard pattern (must contain '*' in template).

        Example:
            CacheKeyManager.make_pattern("brand", "variants_all", id=42)
            → "myproject:brand:variants:42:*"
        """
        raw_template = CacheKeyManager._get_template(resource_name, key_name)
        if "*" not in raw_template:
            logger.error(
                f"[CacheKeyManager] Template for '{resource_name}:{key_name}' "
                f"does not contain '*'; use make_key(...) instead."
            )
            raise ValueError(f"Template '{raw_template}' has no wildcard")
        try:
            filled = raw_template.format(**kwargs)
        except KeyError as e:
            missing = e.args[0]
            logger.error(
                f"[CacheKeyManager] Missing argument '{missing}' when formatting '{raw_template}'"
            )
            raise

        prefix = settings.CACHES["default"].get("KEY_PREFIX", "")
        if prefix:
            return f"{prefix}:{filled}"
        return filled

    @staticmethod
    def get_available_templates(resource_name: str) -> Dict[str, str]:
        """
        Get all available cache key templates for a resource.
        Useful for debugging and documentation.

        Example:
            templates = CacheKeyManager.get_available_templates("brand")
            # Returns: {"detail": "brand:detail:{id}", "stats": "brand:stats:{id}", ...}
        """
        templates = getattr(settings, "CACHE_KEY_TEMPLATES", {})
        return templates.get(resource_name, {})

    @staticmethod
    def validate_template(resource_name: str, key_name: str, **kwargs) -> bool:
        """
        Validate that all required parameters are provided for a template.

        Example:
            valid = CacheKeyManager.validate_template("brand", "detail", id=42)
            # Returns True if all placeholders can be filled
        """
        try:
            CacheKeyManager.make_key(resource_name, key_name, **kwargs)
            return True
        except (KeyError, ValueError):
            return False

    @staticmethod
    def get_template_placeholders(resource_name: str, key_name: str) -> List[str]:
        """
        Extract placeholder names from a template.

        Example:
            placeholders = CacheKeyManager.get_template_placeholders("brand", "analytics")
            # Returns: ["brand_id", "days"]
        """
        import re

        try:
            raw_template = CacheKeyManager._get_template(resource_name, key_name)
            # Find all {placeholder} patterns
            placeholders = re.findall(r"\{([^}]+)\}", raw_template)
            return placeholders
        except KeyError:
            return []

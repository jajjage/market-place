from django.db.models import Count
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings
from typing import List, Dict, Any, Optional

from apps.products.product_base.models import Product


from .models import ProductWatchlistItem


# Cache TTL from settings or default to 5 minutes
CACHE_TTL = getattr(settings, "WATCHLIST_CACHE_TTL", 300)


class WatchlistService:
    """Service class to handle watchlist business logic and complex queries with caching."""

    @staticmethod
    def get_cache_key(view_name: str, **kwargs) -> str:
        """Generate a cache key for the view"""
        user_id = kwargs.get("user_id", "")
        pk = kwargs.get("pk", "")
        product_id = kwargs.get("product_id", "")

        # Create a more specific key based on the view
        key_parts = [str(part) for part in [user_id, pk, product_id] if part]
        key_suffix = ":".join(key_parts) if key_parts else "default"

        return f"watchlist:{view_name}:{key_suffix}"

    @staticmethod
    def get_user_watchlist_queryset(user, user_id: Optional[int] = None):
        """
        Get optimized queryset for user's watchlist with proper select_related.
        """
        if user.is_staff and user_id:
            queryset = ProductWatchlistItem.objects.filter(user_id=user_id)
        else:
            queryset = ProductWatchlistItem.objects.filter(user=user)

        # Always prefetch related data to avoid N+1 queries
        return queryset.select_related(
            "product", "product__category", "user"
        ).prefetch_related("product__images")

    @staticmethod
    def get_watchlist_stats(user, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate watchlist statistics with caching.
        """
        cache_user_id = user_id if user.is_staff and user_id else user.id
        cache_key = WatchlistService.get_cache_key("stats", user_id=cache_user_id)

        # Try to get from cache first
        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            return cached_stats

        base_queryset = WatchlistService.get_user_watchlist_queryset(user, user_id)

        # Single query to get total count
        total_items = base_queryset.count()

        if total_items == 0:
            stats = {
                "total_items": 0,
                "recently_added": [],
                "most_watched_categories": [],
            }
        else:
            # Get recently added items (product IDs only)
            recently_added = list(
                base_queryset.order_by("-added_at")[:5].values_list(
                    "product_id", flat=True
                )
            )

            # Get category statistics
            category_stats = list(
                base_queryset.exclude(product__category__isnull=True)
                .values("product__category__name")
                .annotate(count=Count("id"))
                .order_by("-count")[:5]
            )

            most_watched_categories = [
                {"name": item["product__category__name"], "count": item["count"]}
                for item in category_stats
            ]

            stats = {
                "total_items": total_items,
                "recently_added": recently_added,
                "most_watched_categories": most_watched_categories,
            }

        # Cache the result
        cache.set(cache_key, stats, CACHE_TTL)
        return stats

    @staticmethod
    def is_product_in_watchlist(user, product_id: int) -> bool:
        """
        Check if product is in user's watchlist with caching.
        """
        cache_key = WatchlistService.get_cache_key(
            "check_product", user_id=user.id, product_id=product_id
        )

        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        result = ProductWatchlistItem.objects.filter(
            user=user, product_id=product_id
        ).exists()

        # Cache for shorter time since this can change frequently
        cache.set(cache_key, result, CACHE_TTL // 2)
        return result

    @staticmethod
    def get_product_watchlist_count(product_id: int) -> int:
        """
        Get total watchlist count for a specific product with caching.
        """
        cache_key = WatchlistService.get_cache_key(
            "product_count", product_id=product_id
        )

        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return cached_count

        count = ProductWatchlistItem.objects.filter(product_id=product_id).count()

        # Cache for longer time since this changes less frequently
        cache.set(cache_key, count, CACHE_TTL * 2)
        return count

    @staticmethod
    @transaction.atomic
    def toggle_product_in_watchlist(user, product_id: int) -> Dict[str, str]:
        """
        Toggle product in watchlist and invalidate related cache.
        """
        # Validate product exists and is active
        product = get_object_or_404(Product, id=product_id, is_active=True)

        # Use get_or_create for atomic operation
        watchlist_item, created = ProductWatchlistItem.objects.get_or_create(
            user=user, product=product, defaults={}
        )

        # Invalidate related cache keys
        WatchlistService._invalidate_user_cache(user.id)
        WatchlistService._invalidate_product_cache(product_id)

        if created:
            return {"status": "added", "message": "Product added to watchlist"}
        else:
            watchlist_item.delete()
            return {"status": "removed", "message": "Product removed from watchlist"}

    @staticmethod
    @transaction.atomic
    def bulk_add_products(user, product_ids: List[int]) -> List[ProductWatchlistItem]:
        """
        Bulk add products to watchlist and invalidate cache.
        """
        # Validate all products exist and are active
        valid_products = Product.objects.filter(
            id__in=product_ids, is_active=True
        ).values_list("id", flat=True)

        # Filter out products already in watchlist
        existing_product_ids = set(
            ProductWatchlistItem.objects.filter(
                user=user, product_id__in=valid_products
            ).values_list("product_id", flat=True)
        )

        # Create watchlist items for new products only
        new_product_ids = set(valid_products) - existing_product_ids

        result = []
        if new_product_ids:
            watchlist_items = [
                ProductWatchlistItem(user=user, product_id=product_id)
                for product_id in new_product_ids
            ]
            result = ProductWatchlistItem.objects.bulk_create(
                watchlist_items, ignore_conflicts=True
            )

            # Invalidate cache for user and affected products
            WatchlistService._invalidate_user_cache(user.id)
            for product_id in new_product_ids:
                WatchlistService._invalidate_product_cache(product_id)

        return result

    @staticmethod
    @transaction.atomic
    def bulk_remove_products(user, product_ids: List[int]) -> int:
        """
        Bulk remove products from watchlist and invalidate cache.
        """
        removed_count, _ = ProductWatchlistItem.objects.filter(
            user=user, product_id__in=product_ids
        ).delete()

        if removed_count > 0:
            # Invalidate cache for user and affected products
            WatchlistService._invalidate_user_cache(user.id)
            for product_id in product_ids:
                WatchlistService._invalidate_product_cache(product_id)

        return removed_count

    @staticmethod
    def _invalidate_user_cache(user_id: int):
        """Invalidate all cache keys related to a specific user."""
        cache_keys = [
            WatchlistService.get_cache_key("stats", user_id=user_id),
            # Add other user-specific cache keys as needed
        ]
        cache.delete_many(cache_keys)

    @staticmethod
    def _invalidate_product_cache(product_id: int):
        """Invalidate all cache keys related to a specific product."""
        cache_keys = [
            WatchlistService.get_cache_key("product_count", product_id=product_id),
            # Add other product-specific cache keys as needed
        ]
        cache.delete_many(cache_keys)

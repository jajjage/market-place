# services.py - Enhanced Watchlist Service
import uuid
import logging
from datetime import datetime, timedelta
from django.db.models import Count, Prefetch, Min, Max
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.conf import settings
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from apps.products.product_base.models import Product
from apps.core.utils.cache_manager import CacheManager
from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.products.product_watchlist.utils.exceptions import (
    WatchlistError,
)

from .models import ProductWatchlistItem

logger = logging.getLogger(__name__)

# Cache TTL from settings or default to 5 minutes
CACHE_TTL = getattr(settings, "WATCHLIST_CACHE_TTL", 300)
MAX_WATCHLIST_SIZE = getattr(settings, "MAX_WATCHLIST_SIZE", 1000)
BULK_OPERATION_LIMIT = getattr(settings, "BULK_OPERATION_LIMIT", 100)


@dataclass
class WatchlistStats:
    """Data class for watchlist statistics"""

    total_items: int
    recently_added: List[str]
    most_watched_categories: List[Dict[str, Union[str, int]]]
    oldest_item_date: Optional[datetime] = None
    newest_item_date: Optional[datetime] = None
    categories_count: int = 0


@dataclass
class WatchlistOperationResult:
    """Data class for watchlist operation results"""

    success: bool
    message: str
    status: str
    affected_count: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class WatchlistService:
    """
    Enhanced service class for watchlist operations with proper error handling,
    caching, validation, and monitoring.
    """

    @staticmethod
    def get_cache_key(view_name: str, **kwargs) -> str:
        """Generate a cache key for the view"""
        return CacheKeyManager.make_key("watchlist", view_name, **kwargs)

    @staticmethod
    def validate_user_permissions(user, target_user_id: Optional[str] = None) -> str:
        """
        Validate user permissions and return the effective user ID to use.

        Args:
            user: The requesting user
            target_user_id: Optional user ID for staff operations

        Returns:
            str: The effective user ID to use for operations

        Raises:
            WatchlistValidationError: If validation fails
        """
        try:
            if user.is_staff and target_user_id:
                return target_user_id
            return user.id
        except Exception as e:
            logger.error(f"User permission validation failed: {e}")
            raise WatchlistError("Permission validation failed")

    @staticmethod
    def get_user_watchlist_queryset(
        user, target_user_id: Optional[str] = None, include_inactive: bool = False
    ):
        """
        Get optimized queryset for a user's watchlist with proper select_related.
        """
        try:
            effective_user_id = WatchlistService.validate_user_permissions(
                user, target_user_id
            )

            # 1) Build the base watchlist-item queryset
            if user.is_staff and target_user_id:
                watch_qs = ProductWatchlistItem.objects.filter(
                    user_id=effective_user_id
                )
            else:
                watch_qs = ProductWatchlistItem.objects.filter(user=user)

            # Eager-load the FK to product itself
            # Remove select_related("product") so prefetch can populate a list
            watch_qs = watch_qs.select_related("product")

            # 2) Pull out the product IDs
            watched_product_ids = watch_qs.values_list("product_id", flat=True)

            # 3) Build and optimize a Product queryset for those IDs
            product_qs = Product.objects.filter(pk__in=watched_product_ids)
            from apps.products.product_base.services.product_list_service import (
                ProductListService,
            )

            optimized_product_qs = ProductListService.get_product_queryset(product_qs)

            # 4) Optionally filter out inactive products correctly
            if not include_inactive:
                optimized_product_qs = optimized_product_qs.filter(is_active=True)

            # 5) Prefetch those optimized products onto each watchlist item
            return watch_qs.prefetch_related(
                Prefetch(
                    "product",
                    queryset=optimized_product_qs,
                    to_attr="prefetched_product",
                )
            )

        except Exception as e:
            logger.error(f"Error building watchlist queryset: {e}")
            return ProductWatchlistItem.objects.none()

    @staticmethod
    def get_watchlist_stats(
        user, target_user_id: Optional[str] = None, force_refresh: bool = False
    ) -> WatchlistStats:
        """
        Calculate comprehensive watchlist statistics with caching.

        Args:
            user: The requesting user
            target_user_id: Optional user ID for staff operations
            force_refresh: Whether to bypass cache

        Returns:
            WatchlistStats: Comprehensive statistics object
        """
        try:
            effective_user_id = WatchlistService.validate_user_permissions(
                user, target_user_id
            )
            # Generate cache key
            cache_key = WatchlistService.get_cache_key(
                "stats", user_id=effective_user_id
            )

            # Check cache unless force refresh
            if not force_refresh:
                cached_stats = cache.get(cache_key)
                if cached_stats is not None:
                    logger.info(f"Returning cached stats for user {effective_user_id}")
                    return cached_stats

            # Build queryset
            base_queryset = WatchlistService.get_user_watchlist_queryset(
                user, target_user_id
            )

            # Get basic counts
            total_items = base_queryset.count()

            if total_items == 0:
                stats = WatchlistStats(
                    total_items=0,
                    recently_added=[],
                    most_watched_categories=[],
                    categories_count=0,
                )
            else:
                # Get date range information
                date_info = base_queryset.aggregate(
                    oldest=Min("added_at"), newest=Max("added_at")
                )

                # Get recently added items (limit to prevent memory issues)
                recently_added = list(
                    base_queryset.order_by("-added_at")[:10].values_list(
                        "product_id", flat=True
                    )
                )

                # Get category statistics with proper handling
                category_stats = list(
                    base_queryset.exclude(product__category__isnull=True)
                    .values("product__category__name")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:10]
                )

                most_watched_categories = [
                    {"name": item["product__category__name"], "count": item["count"]}
                    for item in category_stats
                ]

                # Count unique categories
                categories_count = (
                    base_queryset.values("product__category").distinct().count()
                )

                stats = WatchlistStats(
                    total_items=total_items,
                    recently_added=recently_added,
                    most_watched_categories=most_watched_categories,
                    oldest_item_date=date_info["oldest"],
                    newest_item_date=date_info["newest"],
                    categories_count=categories_count,
                )

            # Cache the result
            cache.set(cache_key, stats, CACHE_TTL)
            logger.info(
                f"Generated watchlist stats for user {effective_user_id}: {total_items} items"
            )

            return stats

        except Exception as e:
            logger.error(f"Error generating watchlist stats: {e}")
            # Return empty stats on error
            return WatchlistStats(
                total_items=0,
                recently_added=[],
                most_watched_categories=[],
                categories_count=0,
            )

    @staticmethod
    def is_product_in_watchlist(
        user, product_id: Union[str, uuid.UUID], use_cache: bool = True
    ) -> bool:
        """
        Check if product is in user's watchlist with caching.

        Args:
            user: The user to check for
            product_id: Product ID to check
            use_cache: Whether to use caching

        Returns:
            bool: True if product is in watchlist
        """
        try:
            # Validate product_id
            if isinstance(product_id, str):
                try:
                    product_id = uuid.UUID(product_id)
                except ValueError:
                    logger.warning(f"Invalid product_id format: {product_id}")
                    return False

            if use_cache:
                cache_key = WatchlistService.get_cache_key(
                    "check_product", user_id=user.id, product_id=str(product_id)
                )

                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

            result = ProductWatchlistItem.objects.filter(
                user=user, product_id=product_id, product__is_active=True
            ).exists()

            if use_cache:
                # Cache for shorter time since this can change frequently
                cache.set(cache_key, result, CACHE_TTL // 2)

            return result

        except Exception as e:
            logger.error(f"Error checking product in watchlist: {e}")
            return False

    @staticmethod
    def get_product_watchlist_count(
        product_id: Union[str, uuid.UUID], use_cache: bool = True
    ) -> int:
        """
        Get total watchlist count for a specific product with caching.

        Args:
            product_id: Product ID to get count for
            use_cache: Whether to use caching

        Returns:
            int: Number of users who have this product in their watchlist
        """
        try:
            # Validate product_id
            if isinstance(product_id, str):
                try:
                    product_id = uuid.UUID(product_id)
                except ValueError:
                    logger.warning(f"Invalid product_id format: {product_id}")
                    return 0

            if use_cache:
                cache_key = WatchlistService.get_cache_key(
                    "product_count", product_id=str(product_id)
                )

                cached_count = cache.get(cache_key)
                if cached_count is not None:
                    logger.info(
                        f"Returning cached count for product {product_id}: {cached_count}"
                    )
                    return cached_count

            count = ProductWatchlistItem.objects.filter(
                product_id=product_id, product__is_active=True
            ).count()

            if use_cache:
                # Cache for longer time since this changes less frequently
                cache.set(cache_key, count, CACHE_TTL * 2)

            return count

        except Exception as e:
            logger.error(f"Error getting product watchlist count: {e}")
            return 0

    @staticmethod
    @transaction.atomic
    def add_product_to_watchlist(
        user, product_id: Union[str, uuid.UUID]
    ) -> WatchlistOperationResult:
        """
        Add product to watchlist with comprehensive validation and error handling.

        Args:
            user: The user performing the operation
            product_id: Product ID to add

        Returns:
            WatchlistOperationResult: Result of the operation
        """
        try:
            # Validate product_id format
            if isinstance(product_id, str):
                try:
                    product_id = uuid.UUID(product_id)
                    logger.info(f"Converted product_id to UUID: {product_id}")
                except ValueError:
                    return WatchlistOperationResult(
                        success=False,
                        message="Invalid product ID format",
                        status="error",
                        errors=["Product ID must be a valid UUID"],
                    )

            # Check if user has reached watchlist limit
            current_count = ProductWatchlistItem.objects.filter(user=user).count()
            if current_count >= MAX_WATCHLIST_SIZE:
                return WatchlistOperationResult(
                    success=False,
                    message=f"Watchlist limit reached ({MAX_WATCHLIST_SIZE} items)",
                    status="error",
                    errors=[f"Maximum watchlist size is {MAX_WATCHLIST_SIZE}"],
                )

            # Get or validate product exists and is active
            try:
                product = get_object_or_404(
                    Product, id=product_id, is_active=True, status="active"
                )
                logger.info(f"Found product {product_id} for user {user.id}")
            except Product.DoesNotExist:
                return WatchlistOperationResult(
                    success=False,
                    message="Product not found or inactive",
                    status="error",
                    errors=["Product does not exist or is not active"],
                )

            # Check if already in watchlist
            if ProductWatchlistItem.objects.filter(user=user, product=product).exists():
                return WatchlistOperationResult(
                    success=False,
                    message="Product is already in your watchlist",
                    status="error",
                    errors=["Product already exists in watchlist"],
                )

            # Check if user is the seller of the product
            if product.seller == user:
                return WatchlistOperationResult(
                    success=False,
                    message="You cannot add your own product to the watchlist",
                    status="error",
                    errors=["You cannot add your own product to the watchlist"],
                )

            # Add to watchlist
            watchlist_item = ProductWatchlistItem.objects.create(
                user=user, product=product
            )

            logger.info(f"User {user.id} added product {product_id} to watchlist")

            # Invalidate related cache keys
            WatchlistService._invalidate_caches_for_user_and_product(
                user.id, product_id
            )

            return WatchlistOperationResult(
                success=True,
                message="Product added to watchlist successfully",
                status="added",
                affected_count=1,
            )

        except Exception as e:
            logger.error(f"Error adding product to watchlist: {e}")
            return WatchlistOperationResult(
                success=False,
                message="An error occurred while adding product to watchlist",
                status="error",
                errors=[str(e)],
            )

    @staticmethod
    @transaction.atomic
    def remove_product_from_watchlist(
        user, product_id: Union[str, uuid.UUID]
    ) -> WatchlistOperationResult:
        """
        Remove product from watchlist with comprehensive validation and error handling.

        Args:
            user: The user performing the operation
            product_id: Product ID to remove

        Returns:
            WatchlistOperationResult: Result of the operation
        """
        try:
            # Validate product_id format
            if isinstance(product_id, str):
                try:
                    product_id = uuid.UUID(product_id)
                    logger.info(f"Converted product_id to UUID: {product_id}")
                except ValueError:
                    return WatchlistOperationResult(
                        success=False,
                        message="Invalid product ID format",
                        status="error",
                        errors=["Product ID must be a valid UUID"],
                    )

            # Check if product exists in watchlist
            try:
                watchlist_item = ProductWatchlistItem.objects.get(
                    user=user, product_id=product_id
                )

            except ProductWatchlistItem.DoesNotExist:
                return WatchlistOperationResult(
                    success=False,
                    message="Product is not in your watchlist",
                    status="error",
                    errors=["Product is not in your watchlist"],
                )

            # Remove from watchlist
            watchlist_item.delete()

            logger.info(f"User {user.id} removed product {product_id} from watchlist")

            # Invalidate related cache keys
            WatchlistService._invalidate_caches_for_user_and_product(
                user.id, product_id
            )

            return WatchlistOperationResult(
                success=True,
                message="Product removed from watchlist successfully",
                status="removed",
                affected_count=1,
            )

        except Exception as e:
            logger.error(f"Error removing product from watchlist: {e}")
            return WatchlistOperationResult(
                success=False,
                message="An error occurred while removing product from watchlist",
                status="error",
                errors=[str(e)],
            )

    @staticmethod
    @transaction.atomic
    def toggle_product_in_watchlist(
        user, product_id: Union[str, uuid.UUID]
    ) -> WatchlistOperationResult:
        """
        Toggle product in watchlist with comprehensive validation and error handling.

        Args:
            user: The user performing the operation
            product_id: Product ID to toggle

        Returns:
            WatchlistOperationResult: Result of the operation
        """
        try:
            # Validate product_id format
            if isinstance(product_id, str):
                try:
                    product_id = uuid.UUID(product_id)
                    logger.info(f"Converted product_id to UUID: {product_id}")
                except ValueError:
                    return WatchlistOperationResult(
                        success=False,
                        message="Invalid product ID format",
                        status="error",
                        errors=["Product ID must be a valid UUID"],
                    )

            # Check if user has reached watchlist limit
            current_count = ProductWatchlistItem.objects.filter(user=user).count()

            # Get or validate product exists and is active
            try:
                product = get_object_or_404(
                    Product, id=product_id, is_active=True, status="active"
                )
                logger.info(f"Found product {product_id} for user {user.id}")
            except Product.DoesNotExist:
                return WatchlistOperationResult(
                    success=False,
                    message="Product not found or inactive",
                    status="error",
                    errors=["Product does not exist or is not active"],
                )

            # Check if already in watchlist
            watchlist_item, created = ProductWatchlistItem.objects.get_or_create(
                user=user, product=product, defaults={}
            )
            logger.info(f"created: {created}")
            if created:
                # Check watchlist size limit
                if current_count >= MAX_WATCHLIST_SIZE:
                    # Rollback the creation
                    watchlist_item.delete()
                    return WatchlistOperationResult(
                        success=False,
                        message=f"Watchlist limit reached ({MAX_WATCHLIST_SIZE} items)",
                        status="error",
                        errors=[f"Maximum watchlist size is {MAX_WATCHLIST_SIZE}"],
                    )

                result = WatchlistOperationResult(
                    success=True,
                    message="Product added to watchlist",
                    status="added",
                    affected_count=1,
                )
                logger.info(f"User {user.id} added product {product_id} to watchlist")
            else:
                # Remove from watchlist
                watchlist_item.delete()
                result = WatchlistOperationResult(
                    success=True,
                    message="Product removed from watchlist",
                    status="removed",
                    affected_count=1,
                )
                logger.info(
                    f"User {user.id} removed product {product_id} from watchlist"
                )

            # Invalidate related cache keys
            WatchlistService._invalidate_caches_for_user_and_product(
                user.id, product_id
            )

            return result

        except Exception as e:
            logger.error(f"Error toggling product in watchlist: {e}")
            return WatchlistOperationResult(
                success=False,
                message="An error occurred while updating watchlist",
                status="error",
                errors=[str(e)],
            )

    @staticmethod
    @transaction.atomic
    def bulk_add_products(
        user, product_ids: List[Union[str, uuid.UUID]], validate_limit: bool = True
    ) -> WatchlistOperationResult:
        """
        Bulk add products to watchlist with comprehensive validation.

        Args:
            user: The user performing the operation
            product_ids: List of product IDs to add
            validate_limit: Whether to validate watchlist size limits

        Returns:
            WatchlistOperationResult: Result of the bulk operation
        """
        try:
            # Validate input
            if not product_ids:
                return WatchlistOperationResult(
                    success=False,
                    message="No products provided",
                    status="error",
                    errors=["Product list cannot be empty"],
                )

            if len(product_ids) > BULK_OPERATION_LIMIT:
                return WatchlistOperationResult(
                    success=False,
                    message=f"Too many products. Limit is {BULK_OPERATION_LIMIT}",
                    status="error",
                    errors=["Bulk operation limit exceeded"],
                )

            # Validate and convert product IDs
            validated_product_ids = []
            errors = []

            for pid in product_ids:
                try:
                    if isinstance(pid, str):
                        pid = uuid.UUID(pid)
                    validated_product_ids.append(pid)
                except ValueError:
                    errors.append(f"Invalid product ID format: {pid}")

            if errors:
                return WatchlistOperationResult(
                    success=False,
                    message="Invalid product IDs provided",
                    status="error",
                    errors=errors,
                )

            # Check watchlist size limit
            if validate_limit:
                current_count = ProductWatchlistItem.objects.filter(user=user).count()
                if current_count + len(validated_product_ids) > MAX_WATCHLIST_SIZE:
                    return WatchlistOperationResult(
                        success=False,
                        message=f"Operation would exceed watchlist limit ({MAX_WATCHLIST_SIZE})",
                        status="error",
                        errors=["Watchlist size limit would be exceeded"],
                    )

            # Validate all products exist and are active
            valid_products = set(
                Product.objects.filter(
                    id__in=validated_product_ids, is_active=True
                ).values_list("id", flat=True)
            )

            invalid_products = set(validated_product_ids) - valid_products
            if invalid_products:
                errors.extend(
                    [
                        f"Product not found or inactive: {pid}"
                        for pid in invalid_products
                    ]
                )

            # Filter out products already in watchlist
            existing_product_ids = set(
                ProductWatchlistItem.objects.filter(
                    user=user, product_id__in=valid_products
                ).values_list("product_id", flat=True)
            )

            # Create watchlist items for new products only
            new_product_ids = valid_products - existing_product_ids
            added_count = 0

            if new_product_ids:
                watchlist_items = [
                    ProductWatchlistItem(user=user, product_id=product_id)
                    for product_id in new_product_ids
                ]

                created_items = ProductWatchlistItem.objects.bulk_create(
                    watchlist_items, ignore_conflicts=True
                )
                added_count = len(created_items)

                # Invalidate caches
                for pid in new_product_ids:
                    WatchlistService._invalidate_caches_for_user_and_product(
                        user.id, pid
                    )

                logger.info(
                    f"User {user.id} bulk added {added_count} products to watchlist"
                )

            # Prepare result
            message_parts = []
            if added_count > 0:
                message_parts.append(f"Added {added_count} products")
            if existing_product_ids:
                message_parts.append(
                    f"{len(existing_product_ids)} already in watchlist"
                )

            return WatchlistOperationResult(
                success=True,
                message=(
                    "; ".join(message_parts) if message_parts else "No changes made"
                ),
                status="completed",
                affected_count=added_count,
                errors=errors if errors else [],
            )

        except Exception as e:
            logger.error(f"Error in bulk add operation: {e}")
            return WatchlistOperationResult(
                success=False,
                message="An error occurred during bulk add operation",
                status="error",
                errors=[str(e)],
            )

    @staticmethod
    @transaction.atomic
    def bulk_remove_products(
        user, product_ids: List[Union[str, uuid.UUID]]
    ) -> WatchlistOperationResult:
        """
        Bulk remove products from watchlist with validation.

        Args:
            user: The user performing the operation
            product_ids: List of product IDs to remove

        Returns:
            WatchlistOperationResult: Result of the bulk operation
        """
        try:
            # Validate input
            if not product_ids:
                return WatchlistOperationResult(
                    success=False,
                    message="No products provided",
                    status="error",
                    errors=["Product list cannot be empty"],
                )

            if len(product_ids) > BULK_OPERATION_LIMIT:
                return WatchlistOperationResult(
                    success=False,
                    message=f"Too many products. Limit is {BULK_OPERATION_LIMIT}",
                    status="error",
                    errors=["Bulk operation limit exceeded"],
                )

            # Validate and convert product IDs
            validated_product_ids = []
            errors = []

            for pid in product_ids:
                try:
                    if isinstance(pid, str):
                        pid = uuid.UUID(pid)
                    validated_product_ids.append(pid)
                except ValueError:
                    errors.append(f"Invalid product ID format: {pid}")

            if errors:
                return WatchlistOperationResult(
                    success=False,
                    message="Invalid product IDs provided",
                    status="error",
                    errors=errors,
                )

            # Perform bulk delete
            removed_count, _ = ProductWatchlistItem.objects.filter(
                user=user, product_id__in=validated_product_ids
            ).delete()

            if removed_count > 0:
                # Invalidate caches
                for pid in validated_product_ids:
                    WatchlistService._invalidate_caches_for_user_and_product(
                        user.id, pid
                    )

                logger.info(
                    f"User {user.id} bulk removed {removed_count} products from watchlist"
                )

            return WatchlistOperationResult(
                success=True,
                message=f"Removed {removed_count} products from watchlist",
                status="completed",
                affected_count=removed_count,
            )

        except Exception as e:
            logger.error(f"Error in bulk remove operation: {e}")
            return WatchlistOperationResult(
                success=False,
                message="An error occurred during bulk remove operation",
                status="error",
                errors=[str(e)],
            )

    @staticmethod
    def _invalidate_caches_for_user_and_product(
        user_id: uuid.UUID, product_id: uuid.UUID
    ):
        """
        Invalidate all relevant cache keys for user and product operations.

        Args:
            user_id: User ID whose caches to invalidate
            product_id: Product ID whose caches to invalidate
        """
        try:
            # User-specific cache keys
            user_cache_keys = [
                WatchlistService.get_cache_key("stats", user_id=user_id),
                WatchlistService.get_cache_key(
                    "check_product", user_id=user_id, product_id=str(product_id)
                ),
            ]

            # Product-specific cache keys
            product_cache_keys = [
                WatchlistService.get_cache_key(
                    "product_count", product_id=str(product_id)
                ),
            ]

            all_keys = user_cache_keys + product_cache_keys
            cache.delete_many(all_keys)

            # Use CacheManager for broader invalidation
            CacheManager.invalidate("watchlist", user_id=user_id)
            CacheManager.invalidate("watchlist", product_id=product_id)

            logger.debug(
                f"Invalidated {len(all_keys)} cache keys for user {user_id} and product {product_id}"
            )

        except Exception as e:
            logger.error(f"Error invalidating caches: {e}")

    @staticmethod
    def get_watchlist_insights(
        user, target_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get advanced watchlist insights and analytics.

        Args:
            user: The requesting user
            target_user_id: Optional user ID for staff operations

        Returns:
            Dict containing advanced insights
        """
        try:
            effective_user_id = WatchlistService.validate_user_permissions(
                user, target_user_id
            )
            cache_key = WatchlistService.get_cache_key(
                "insights", user_id=effective_user_id
            )

            cached_insights = cache.get(cache_key)
            if cached_insights is not None:
                return cached_insights

            queryset = WatchlistService.get_user_watchlist_queryset(
                user, target_user_id
            )

            # Calculate insights
            total_items = queryset.count()

            if total_items == 0:
                insights = {
                    "total_items": 0,
                    "activity_summary": "No watchlist activity",
                    "recommendations": ["Start adding products to your watchlist"],
                }
            else:
                # Time-based analysis
                now = datetime.now()
                last_week = now - timedelta(days=7)
                last_month = now - timedelta(days=30)

                recent_additions = queryset.filter(added_at__gte=last_week).count()
                monthly_additions = queryset.filter(added_at__gte=last_month).count()

                # Category distribution
                category_distribution = list(
                    queryset.values("product__category__name")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                )

                # Price range analysis (if price field exists)
                # This would depend on your Product model structure

                insights = {
                    "total_items": total_items,
                    "recent_activity": {
                        "last_week": recent_additions,
                        "last_month": monthly_additions,
                    },
                    "category_distribution": category_distribution[:10],
                    "activity_summary": f"{recent_additions} items added this week",
                    "recommendations": WatchlistService._generate_recommendations(
                        queryset, category_distribution
                    ),
                }

            cache.set(cache_key, insights, CACHE_TTL)
            return insights

        except Exception as e:
            logger.error(f"Error generating watchlist insights: {e}")
            return {"error": "Unable to generate insights"}

    @staticmethod
    def _generate_recommendations(queryset, category_distribution) -> List[str]:
        """Generate personalized recommendations based on watchlist data."""
        recommendations = []

        try:
            total_items = queryset.count()

            if total_items > 50:
                recommendations.append(
                    "Consider organizing your watchlist by removing items you're no longer interested in"
                )
            elif total_items < 5:
                recommendations.append(
                    "Explore more products to build a diverse watchlist"
                )

            if category_distribution:
                top_category = category_distribution[0]["product__category__name"]
                recommendations.append(
                    f"You seem interested in {top_category}. Check out our latest arrivals in this category"
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Keep exploring products that interest you"]

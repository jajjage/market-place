from django.db import transaction, models
from django.db.models import Count, Avg, Q
from django.core.cache import cache
from django.conf import settings
from typing import List, Dict, Any
import logging

from .models import ProductCondition
from apps.products.product_base.models import Product
from apps.core.utils.cache_manager import CacheManager
from apps.core.utils.cache_key_manager import CacheKeyManager

logger = logging.getLogger(__name__)

CACHE_TTL = getattr(settings, "CONDITIONS_CACHE_TTL", 300)


class ProductConditionService:
    """
    Business logic service for ProductCondition operations.
    """

    CACHE_TIMEOUT = getattr(settings, "CONDITION_CACHE_TIMEOUT", 1800)  # 30 minutes

    @classmethod
    def get_active_conditions(
        cls, include_stats: bool = False
    ) -> List[ProductCondition]:
        """Get all active conditions with optional statistics."""
        if CacheManager.cache_exists(
            "product_condition", "active_conditions", include_stats=include_stats
        ):
            cache_key = CacheKeyManager.make_key(
                "product_condition", "active_conditions", include_stats=include_stats
            )
            cached_result = cache.get(cache_key)
            return cached_result

        queryset = ProductCondition.objects.filter(is_active=True)

        if include_stats:
            queryset = queryset.annotate(
                products_count=Count("products", filter=Q(products__is_active=True)),
                avg_price=Avg("products__price", filter=Q(products__is_active=True)),
            ).select_related("created_by")

        conditions = queryset.order_by("display_order", "name")
        cache_key = CacheKeyManager.make_key(
            "product_condition", "active_conditions", include_stats=include_stats
        )
        cache.set(cache_key, conditions, cls.CACHE_TIMEOUT)

        return conditions

    @classmethod
    def get_popular_conditions(cls, limit: int = 10) -> List[ProductCondition]:
        """Get most popular conditions based on product usage."""
        if CacheManager.cache_exists(
            "product_condition", "popular_conditions", limit=limit
        ):
            cache_key = CacheKeyManager.make_key(
                "product_condition", "popular_conditions", limit=limit
            )
            cached_result = cache.get(cache_key)

            if cached_result:
                return cached_result

        conditions = (
            ProductCondition.objects.annotate(
                products_count=Count("product", filter=Q(product__is_active=True)),
                avg_rating=Avg(
                    "product__average_rating", filter=Q(product__is_active=True)
                ),
            )
            .filter(is_active=True, products_count__gt=0)
            .order_by("-products_count", "-avg_rating")[:limit]
        )

        result = list(conditions)
        cache_key = CacheKeyManager.make_key(
            "product_condition", "popular_conditions", limit=limit
        )
        cache.set(cache_key, result, cls.CACHE_TIMEOUT)
        return result

    @classmethod
    def get_condition_analytics(cls, condition_id: int) -> Dict[str, Any]:
        """Get detailed analytics for a specific condition."""
        if CacheManager.cache_exists(
            "product_condition", "analytics", condition_id=condition_id
        ):
            cache_key = CacheKeyManager.make_key(
                "product_condition", "analytics", condition_id=condition_id
            )
            cached_result = cache.get(cache_key)

            if cached_result:
                return cached_result

        try:
            condition = ProductCondition.objects.get(id=condition_id, is_active=True)
        except ProductCondition.DoesNotExist:
            return None

        # Get product statistics
        products = Product.objects.filter(condition=condition, is_active=True)

        analytics = {
            "condition": condition,
            "total_products": products.count(),
            "avg_price": products.aggregate(avg_price=Avg("price"))["avg_price"] or 0,
            "price_range": products.aggregate(
                min_price=models.Min("price"), max_price=models.Max("price")
            ),
            "categories_count": products.values("category").distinct().count(),
            "avg_rating": products.aggregate(avg_rating=Avg("average_rating"))[
                "avg_rating"
            ]
            or 0,
            "stock_status": {
                "in_stock": products.filter(stock_quantity__gt=0).count(),
                "low_stock": products.filter(
                    stock_quantity__lte=5, stock_quantity__gt=0
                ).count(),
                "out_of_stock": products.filter(stock_quantity=0).count(),
            },
        }
        cache_key = CacheKeyManager.make_key(
            "product_condition", "analytics", condition_id=condition_id
        )
        cache.set(cache_key, analytics, cls.CACHE_TIMEOUT)
        return analytics

    @classmethod
    def get_condition_with_products(
        cls, condition_id: int, filters: Dict[str, Any] = None
    ) -> Dict:
        """Get condition with filtered products."""
        try:
            condition = ProductCondition.objects.get(id=condition_id, is_active=True)
        except ProductCondition.DoesNotExist:
            return None

        # Build product queryset
        products = Product.objects.filter(condition=condition, is_active=True)

        # Apply filters
        if filters:
            products = cls._apply_product_filters(products, filters)

        # Optimize queryset
        products = products.select_related(
            "category", "brand", "condition"
        ).prefetch_related("images")

        return {"condition": condition, "products": products}

    @classmethod
    def create_condition(cls, data: Dict[str, Any], user=None) -> ProductCondition:
        """Create a new condition with validation."""
        with transaction.atomic():
            # Auto-generate slug if not provided
            if "slug" not in data and "name" in data:
                from django.utils.text import slugify

                data["slug"] = slugify(data["name"])

            # Set creator
            if user:
                data["created_by"] = user

            condition, created = ProductCondition.objects.get_or_create(**data)
            cls._clear_condition_caches()

            return condition

    @classmethod
    def update_condition(
        cls, condition_id: int, data: Dict[str, Any]
    ) -> ProductCondition:
        """Update condition with cache invalidation."""
        with transaction.atomic():
            condition = ProductCondition.objects.get(id=condition_id)

            for key, value in data.items():
                setattr(condition, key, value)

            condition.save()
            cls._clear_condition_caches()

            return condition

    @classmethod
    def bulk_update_display_order(cls, condition_orders: List[Dict[str, int]]) -> bool:
        """Bulk update display order for conditions."""
        with transaction.atomic():
            for item in condition_orders:
                ProductCondition.objects.filter(id=item["id"]).update(
                    display_order=item["order"]
                )

            cls._clear_condition_caches()
            return True

    @classmethod
    def get_conditions_by_quality_range(
        cls, min_score: int, max_score: int
    ) -> List[ProductCondition]:
        """Get conditions within a quality score range."""
        return ProductCondition.objects.filter(
            is_active=True, quality_score__gte=min_score, quality_score__lte=max_score
        ).order_by("-quality_score")

    @classmethod
    def suggest_condition_price(cls, product_price: float, condition_id: int) -> float:
        """Suggest price based on condition's price factor."""
        try:
            condition = ProductCondition.objects.get(id=condition_id)
            return float(product_price) * float(condition.price_factor)
        except ProductCondition.DoesNotExist:
            return product_price

    @classmethod
    def _apply_product_filters(cls, queryset, filters: Dict[str, Any]):
        """Apply filters to product queryset."""
        if "category" in filters:
            queryset = queryset.filter(category__slug=filters["category"])

        if "price_min" in filters:
            queryset = queryset.filter(price__gte=filters["price_min"])

        if "price_max" in filters:
            queryset = queryset.filter(price__lte=filters["price_max"])

        if "brand" in filters:
            queryset = queryset.filter(brand__slug=filters["brand"])

        if "in_stock" in filters and filters["in_stock"]:
            queryset = queryset.filter(stock_quantity__gt=0)

        if "rating_min" in filters:
            queryset = queryset.filter(average_rating__gte=filters["rating_min"])

        return queryset

    @classmethod
    def _clear_condition_caches(cls):
        """Clear all condition-related caches using the centralized manager."""
        CacheManager.invalidate("product_condition")

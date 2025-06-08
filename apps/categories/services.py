from django.db import transaction
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.conf import settings
from typing import List, Dict, Optional, Any
import logging

from apps.categories.models import Category
from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.core.utils.cache_manager import CacheManager
from apps.products.product_base.models import Product

logger = logging.getLogger(__name__)

CACHE_TTL = getattr(settings, "CATEGORIES_CACHE_TTL", 300)


class CategoryService:
    """
    Business logic service for Category operations.
    Handles complex queries, caching, and business rules.
    """

    CACHE_TIMEOUT = getattr(settings, "CATEGORY_CACHE_TIMEOUT", 3600)  # 1 hour

    @classmethod
    def get_category_tree(
        cls, max_depth: int = 3, include_inactive: bool = False
    ) -> List[Dict]:
        """
        Get hierarchical category tree with optimized queries and caching.
        """
        if CacheManager.cache_exists(
            "category", "tree", max_depth=max_depth, include_inactive=include_inactive
        ):
            cache_key = CacheKeyManager.make_key(
                "category",
                "tree",
                max_depth=max_depth,
                include_inactive=include_inactive,
            )
            cached_result = cache.get(cache_key)
            return cached_result

        # Build optimized queryset with prefetch
        base_queryset = Category.objects.select_related("parent")

        if not include_inactive:
            base_queryset = base_queryset.filter(is_active=True)

        # Get root categories with all descendants in one query
        root_categories = base_queryset.filter(parent=None).prefetch_related(
            Prefetch(
                "subcategories",
                queryset=cls._get_nested_subcategories_queryset(
                    max_depth - 1, include_inactive
                ),
                to_attr="prefetched_subcategories",
            )
        )

        def build_tree_data(categories, current_depth=0):
            if current_depth >= max_depth:
                return []

            result = []
            for category in categories:
                category_data = {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                    "slug": category.slug,
                    "is_active": category.is_active,
                    "subcategories": [],
                }

                if (
                    hasattr(category, "prefetched_subcategories")
                    and current_depth < max_depth - 1
                ):
                    category_data["subcategories"] = build_tree_data(
                        category.prefetched_subcategories, current_depth + 1
                    )

                result.append(category_data)

            return result

        tree_data = build_tree_data(root_categories)
        cache_key = CacheKeyManager.make_key(
            "category", "tree", max_depth=max_depth, include_inactive=include_inactive
        )
        cache.set(cache_key, tree_data, cls.CACHE_TIMEOUT)

        return tree_data

    @classmethod
    def _get_nested_subcategories_queryset(
        cls, depth: int, include_inactive: bool = False
    ):
        """Helper to build nested prefetch queryset."""
        if depth <= 0:
            return Category.objects.none()

        queryset = Category.objects.select_related("parent")

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        if depth > 1:
            queryset = queryset.prefetch_related(
                Prefetch(
                    "subcategories",
                    queryset=cls._get_nested_subcategories_queryset(
                        depth - 1, include_inactive
                    ),
                    to_attr="prefetched_subcategories",
                )
            )

        return queryset

    @classmethod
    def get_category_with_products(
        cls,
        category_id: int,
        include_subcategories: bool = False,
        filters: Dict[str, Any] = None,
    ) -> Dict:
        """
        Get category with its products, optimized with select_related and prefetch_related.
        """
        try:
            category = Category.objects.select_related("parent").get(
                id=category_id, is_active=True
            )
        except Category.DoesNotExist:
            return None

        # Build product queryset
        if include_subcategories:
            category_ids = cls.get_all_subcategory_ids(category_id)
            product_queryset = Product.objects.filter(
                category_id__in=category_ids, is_active=True
            )
        else:
            product_queryset = Product.objects.filter(category=category, is_active=True)

        # Apply additional filters
        if filters:
            product_queryset = cls._apply_product_filters(product_queryset, filters)

        # Optimize product queries
        product_queryset = product_queryset.select_related(
            "category", "brand"
        ).prefetch_related("images", "variants")

        return {"category": category, "products": product_queryset}

    @classmethod
    def get_all_subcategory_ids(cls, category_id: int) -> List[int]:
        """
        Get all subcategory IDs recursively using a single query.
        More efficient than recursive function calls.
        """
        if CacheManager.cache_exists(
            "category", "subcategory_ids", category_id=category_id
        ):
            cache_key = CacheKeyManager.make_key(
                "category", "subcategory_ids", category_id=category_id
            )
            cached_result = cache.get(cache_key)
            return cached_result

        # Use CTE (Common Table Expression) for PostgreSQL or recursive query
        # This is more efficient than multiple queries
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH RECURSIVE subcategories AS (
                    SELECT id FROM categories WHERE id = %s
                    UNION ALL
                    SELECT c.id FROM categories c
                    INNER JOIN subcategories s ON c.parent_id = s.id
                )
                SELECT id FROM subcategories
            """,
                [category_id],
            )

            category_ids = [row[0] for row in cursor.fetchall()]

        cache_key = CacheKeyManager.make_key(
            "category", "subcategory_ids", category_id=category_id
        )
        cache.set(cache_key, category_ids, cls.CACHE_TIMEOUT)
        return category_ids

    @classmethod
    def get_popular_categories(cls, limit: int = 10) -> List[Category]:
        """Get popular categories with product counts."""
        if CacheManager.cache_exists("category", "popular_categories", limit=limit):
            cache_key = CacheKeyManager.make_key(
                "category", "popular_categories", limit=limit
            )
            cached_result = cache.get(cache_key)

            if cached_result:
                return cached_result

        categories = (
            Category.objects.select_related("parent")
            .annotate(product_count=Count("product", filter=Q(product__is_active=True)))
            .filter(is_active=True, product_count__gt=0)
            .order_by("-product_count")[:limit]
        )
        cache_key = CacheKeyManager.make_key(
            "category", "popular_categories", limit=limit
        )
        cache.set(cache_key, list(categories), cls.CACHE_TIMEOUT)
        return categories

    @classmethod
    def get_breadcrumb_path(cls, category_id: int) -> List[Dict]:
        """Get breadcrumb path for a category with improved caching."""
        if CacheManager.cache_exists(
            "category", "breadcrumb_path", category_id=category_id
        ):
            cache_key = CacheKeyManager.make_key(
                "category", "breadcrumb_path", category_id=category_id
            )
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result

        try:
            # Fixed: Should query Category, not Product
            from apps.categories.models import Category

            category = Category.objects.select_related("parent").get(id=category_id)
        except Category.DoesNotExist:
            return []

        breadcrumbs = []
        current = category

        # Build path from current to root
        while current:
            breadcrumbs.insert(
                0, {"id": current.id, "name": current.name, "slug": current.slug}
            )
            current = current.parent

        # Cache the result
        cache_key = CacheKeyManager.make_key(
            "category", "breadcrumb_path", category_id=category_id
        )
        cache.set(cache_key, breadcrumbs, cls.CACHE_TIMEOUT)
        return breadcrumbs

    @classmethod
    def invalidate_breadcrumb_cache(cls, category_id: int):
        """Invalidate breadcrumb cache when category changes."""
        cache_key = CacheKeyManager.make_key(
            "category", "breadcrumb_path", category_id=category_id
        )
        cache.delete(cache_key)

    @classmethod
    def create_category(cls, data: Dict[str, Any], user=None) -> Category:
        """Create a new category with validation."""
        with transaction.atomic():
            # Validate parent relationship
            if "parent" in data and data["parent"]:
                cls._validate_parent_relationship(None, data["parent"])

            category = Category.objects.create(**data)

            # Clear related caches
            CacheManager.invalidate("category", category_id=category.id)

            return category

    @classmethod
    def update_category(cls, category_id: int, data: Dict[str, Any]) -> Category:
        """Update category with validation."""
        with transaction.atomic():
            category = Category.objects.get(id=category_id)

            # Validate parent relationship if changing parent
            if "parent" in data:
                cls._validate_parent_relationship(category, data["parent"])

            for key, value in data.items():
                setattr(category, key, value)

            category.save()

            # Clear related caches
            CacheManager.invalidate("category", category_id=category_id)

            return category

    @classmethod
    def _validate_parent_relationship(
        cls, instance: Optional[Category], parent: Optional[Category]
    ):
        """Validate parent-child relationship to prevent circular references."""
        if not parent:
            return

        if instance and instance.id == parent.id:
            raise ValueError("A category cannot be its own parent.")

        # Check for circular reference
        current = parent
        while current and current.parent:
            if instance and current.parent.id == instance.id:
                raise ValueError("Circular reference detected in category hierarchy.")
            current = current.parent

    @classmethod
    def _apply_product_filters(cls, queryset, filters: Dict[str, Any]):
        """Apply additional filters to product queryset."""
        if "price_min" in filters:
            queryset = queryset.filter(price__gte=filters["price_min"])

        if "price_max" in filters:
            queryset = queryset.filter(price__lte=filters["price_max"])

        if "brand" in filters:
            queryset = queryset.filter(brand__slug=filters["brand"])

        if "in_stock" in filters and filters["in_stock"]:
            queryset = queryset.filter(stock_quantity__gt=0)

        return queryset

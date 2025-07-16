from django.db import transaction
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.conf import settings
from typing import List, Dict, Optional, Any
import logging
from django.core.exceptions import ValidationError
from django.utils.text import slugify

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
    def get_categories(
        cls, base_queryset, include_inactive: bool = False
    ) -> List[Dict]:
        """
        Get category list with optimized queries and caching.
        """
        if CacheManager.cache_exists(
            "category", "list", include_inactive=include_inactive
        ):
            cache_key = CacheKeyManager.make_key(
                "category",
                "list",
                include_inactive=include_inactive,
            )
            cached_result = cache.get(cache_key)
            return cached_result

        if not include_inactive:
            base_queryset = base_queryset.filter(is_active=True)

        # Get root categories with all descendants in one query
        root_categories = base_queryset.prefetch_related("subcategories")
        cache_key = CacheKeyManager.make_key(
            "category", "list", include_inactive=include_inactive
        )
        cache.set(cache_key, root_categories, cls.CACHE_TIMEOUT)
        logger.info(f"categories: {root_categories}")
        return root_categories

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
            .annotate(
                product_count=Count("products", filter=Q(products__is_active=True))
            )
            .filter(is_active=True, product_count__gt=0)
            .order_by("-product_count")[:limit]
        )
        cache_key = CacheKeyManager.make_key(
            "category", "popular_categories", limit=limit
        )
        cache.set(cache_key, list(categories), cls.CACHE_TIMEOUT)
        return categories

    @classmethod
    def create_category(cls, data: Dict[str, Any]) -> Category:
        """Create a single category with validation."""
        with transaction.atomic():
            # Validate parent relationship if parent is provided
            if "parent" in data and data["parent"] is not None:
                cls._validate_parent_relationship(None, data["parent"])

            # Create the category
            category = Category.objects.create(**data)

            # Clear related caches
            CacheManager.invalidate_key("category", "list", include_inactive=False)
            if category.parent:
                CacheManager.invalidate("category", "list", include_inactive=False)

            return category

    @classmethod
    def bulk_create_categories(cls, categories_data):
        """
        Optimized bulk create method that minimizes database queries,
        and assigns unique slugs before bulk insertion.
        """
        if not categories_data:
            return []

        created_categories = []

        try:
            logger.info(f"Bulk creating {len(categories_data)} categories")

            with transaction.atomic():
                # --- STEP 1: PRE‐VALIDATE PARENTS (unchanged) ---
                parent_ids = []
                for i, data in enumerate(categories_data):
                    if not isinstance(data, dict):
                        raise ValidationError(
                            f"Category data at index {i} must be a dictionary, got {type(data)}"
                        )
                    pid = data.get("parent")
                    if pid is not None:
                        parent_ids.append(pid.id if hasattr(pid, "id") else pid)
                if parent_ids:
                    unique_parent_ids = set(parent_ids)
                    existing_parents = {
                        p.id: p
                        for p in Category.objects.filter(id__in=unique_parent_ids)
                    }
                    for pid in unique_parent_ids:
                        if pid not in existing_parents:
                            raise ValidationError(
                                f"Parent category ID {pid} does not exist"
                            )
                        cls._validate_parent_relationship(None, existing_parents[pid])

                # --- STEP 2: BUILD INSTANCES ---
                categories_to_create = []
                valid_fields = {f.name for f in Category._meta.get_fields()}
                for i, data in enumerate(categories_data):
                    if not isinstance(data, dict):
                        raise ValidationError(
                            f"Category data at index {i} must be a dict"
                        )
                    clean = {k: v for k, v in data.items() if k in valid_fields}
                    categories_to_create.append(Category(**clean))

                # --- STEP 3: GENERATE UNIQUE SLUGS ---
                if categories_to_create:
                    # Fetch all existing slugs
                    existing_slugs = set(
                        Category.objects.values_list("slug", flat=True).exclude(
                            slug__exact=""
                        )
                    )
                    new_slugs = []
                    for cat in categories_to_create:
                        base = slugify(cat.name) or "item"
                        slug = base
                        counter = 1
                        # avoid collisions with DB and this batch
                        while slug in existing_slugs or slug in new_slugs:
                            slug = f"{base}-{counter}"
                            counter += 1
                        new_slugs.append(slug)
                        existing_slugs.add(slug)

                    # Assign
                    for cat, slug in zip(categories_to_create, new_slugs):
                        cat.slug = slug

                # --- STEP 4: BULK CREATE ---
                created_categories = Category.objects.bulk_create(
                    categories_to_create,
                    batch_size=1000,
                    ignore_conflicts=False,
                )
                logger.info(f"Bulk created {len(created_categories)} categories")

                # --- STEP 5: REFETCH WITH RELATEDS (if needed) ---
                if created_categories:
                    names = [c.name for c in created_categories]
                    created_categories = list(
                        Category.objects.select_related("parent")
                        .prefetch_related("subcategories")
                        .filter(name__in=names)
                        .order_by("-id")
                    )

                # --- STEP 6: CACHE INVALIDATION ---
                CacheManager.invalidate_key("category", "list", include_inactive=False)
                logger.info("Category list cache invalidated")

                return created_categories

        except ValidationError:
            logger.error("Validation error in bulk create", exc_info=True)
            raise
        except Exception:
            logger.error("Unexpected error in bulk create", exc_info=True)
            raise

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
            CacheManager.invalidate_key("category", "list", include_inactive=False)

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

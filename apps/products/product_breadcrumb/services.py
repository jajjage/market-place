from datetime import time
import logging
from typing import List, Dict, Any
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.core.utils.cache_manager import CacheManager
from django.core.cache import cache
from .models import Breadcrumb

logger = logging.getLogger("breadcrumbs_performance")


class BreadcrumbService:
    """
    Service for managing breadcrumb operations with caching and optimization
    """

    @staticmethod
    def get_product_breadcrumbs(product_id: int) -> List[Dict[str, Any]]:
        """Get breadcrumbs for a specific product with caching"""
        start_time = time.time()

        # Try cache first
        cache_key = CacheKeyManager.make_key(
            "breadcrumb", "product", product_id=product_id
        )
        cached_breadcrumbs = cache.get(cache_key)

        if cached_breadcrumbs:
            logger.info(f"Retrieved breadcrumbs from cache for product {product_id}")
            return cached_breadcrumbs

        # Query database with select_related for optimization
        breadcrumbs = list(
            Breadcrumb.objects.filter(product_id=product_id)
            .select_related("product")
            .values("name", "href", "order")
            .order_by("order")
        )

        # Cache for 1 hour
        cache.set(cache_key, breadcrumbs, 3600)

        end_time = time.time()
        logger.info(
            f"Fetched {len(breadcrumbs)} breadcrumbs for product {product_id} in {(end_time - start_time) * 1000:.2f}ms"
        )

        return breadcrumbs

    @staticmethod
    def bulk_create_breadcrumbs(
        product_id: int, breadcrumb_data: List[Dict[str, Any]]
    ) -> List[Breadcrumb]:
        """Bulk create breadcrumbs for a product"""
        start_time = time.time()

        try:
            with transaction.atomic():
                # Delete existing breadcrumbs
                Breadcrumb.objects.filter(product_id=product_id).delete()

                # Create new breadcrumbs
                breadcrumbs_to_create = []
                for i, data in enumerate(breadcrumb_data):
                    breadcrumbs_to_create.append(
                        Breadcrumb(
                            product_id=product_id,
                            name=data["name"],
                            href=data["href"],
                            order=data.get("order", i),
                        )
                    )

                created_breadcrumbs = Breadcrumb.objects.bulk_create(
                    breadcrumbs_to_create
                )

                # Invalidate cache
                CacheManager.invalidate("breadcrumb", product_id=product_id)

                end_time = time.time()
                logger.info(
                    f"Bulk created {len(created_breadcrumbs)} breadcrumbs for product {product_id} in {(end_time - start_time) * 1000:.2f}ms"
                )

                return created_breadcrumbs

        except Exception as e:
            logger.error(
                f"Error bulk creating breadcrumbs for product {product_id}: {str(e)}"
            )
            raise ValidationError(f"Failed to create breadcrumbs: {str(e)}")

    @staticmethod
    def update_breadcrumb(breadcrumb_id: int, data: Dict[str, Any]) -> Breadcrumb:
        """Update a single breadcrumb"""
        try:
            breadcrumb = Breadcrumb.objects.select_related("product").get(
                id=breadcrumb_id
            )

            for field, value in data.items():
                if hasattr(breadcrumb, field):
                    setattr(breadcrumb, field, value)

            breadcrumb.save()

            # Invalidate cache for the product
            CacheManager.invalidate("breadcrumb", product_id=breadcrumb.product_id)

            logger.info(f"Updated breadcrumb {breadcrumb_id}")
            return breadcrumb

        except Breadcrumb.DoesNotExist:
            raise ValidationError("Breadcrumb not found")

    @staticmethod
    def delete_breadcrumb(breadcrumb_id: int):
        """Delete a breadcrumb"""
        try:
            breadcrumb = Breadcrumb.objects.get(id=breadcrumb_id)
            product_id = breadcrumb.product_id
            breadcrumb.delete()

            # Invalidate cache
            CacheManager.invalidate("breadcrumb", product_id=product_id)

            logger.info(f"Deleted breadcrumb {breadcrumb_id}")

        except Breadcrumb.DoesNotExist:
            raise ValidationError("Breadcrumb not found")

    @staticmethod
    def create_default_breadcrumbs(product) -> List[Breadcrumb]:
        """Create default breadcrumbs based on product category structure"""
        default_breadcrumbs = [
            {"name": "TrustLock", "href": "/", "order": 0},
        ]

        # Add category-based breadcrumbs if product has category
        if hasattr(product, "category") and product.category:
            category = product.category
            category_breadcrumbs = []

            # Build category hierarchy
            categories = []
            current_category = category
            while current_category:
                categories.append(current_category)
                current_category = getattr(current_category, "parent", None)

            # Reverse to get root to leaf order
            categories.reverse()

            for i, cat in enumerate(categories):
                category_breadcrumbs.append(
                    {
                        "name": cat.name,
                        "href": f"/explore?category={cat.slug}",
                        "order": i + 1,
                    }
                )

            default_breadcrumbs.extend(category_breadcrumbs)

        return BreadcrumbService.bulk_create_breadcrumbs(
            product.id, default_breadcrumbs
        )

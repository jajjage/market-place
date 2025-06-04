import time
import logging
from typing import Dict, List
from django.db import models
from django.db.models import QuerySet
from django.core.cache import cache
from django.db import transaction
from itertools import groupby
from operator import attrgetter
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.products.product_base.models import Product
from apps.products.product_detail.models import ProductDetail, ProductDetailTemplate

logger = logging.getLogger("detail_performance")


class ProductDetailService:
    """Centralized service for ProductDetail operations"""

    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def get_product_details(
        product_id: int, detail_type: str = None, highlighted_only: bool = False
    ) -> QuerySet:
        """Get product details with optional filtering"""
        start_time = time.time()

        cache_key = CacheKeyManager.make_key(
            "product_detail",
            "list",
            product_id=product_id,
            detail_type=detail_type or "all",
            highlighted=highlighted_only,
        )

        cached_data = cache.get(cache_key)
        if cached_data:
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Cache hit for product {product_id} details in {duration:.2f}ms"
            )
            return cached_data

        queryset = ProductDetail.objects.select_related("product", "template").filter(
            product_id=product_id, is_active=True
        )

        if detail_type:
            queryset = queryset.filter(detail_type=detail_type)

        if highlighted_only:
            queryset = queryset.filter(is_highlighted=True)

        result = list(queryset.order_by("display_order", "label"))

        cache.set(cache_key, result, ProductDetailService.CACHE_TIMEOUT)

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"Fetched {len(result)} details for product {product_id} in {duration:.2f}ms"
        )

        return result

    @staticmethod
    def get_grouped_details(product_id: int) -> Dict[str, List]:
        """Group details by type for structured frontend consumption"""
        start_time = time.time()

        cache_key = CacheKeyManager.make_key(
            "product_detail", "grouped", product_id=product_id
        )
        cached_data = cache.get(cache_key)

        if cached_data:
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"Cache hit for grouped details product {product_id} in {duration:.2f}ms"
            )
            return cached_data

        details = ProductDetailService.get_product_details(product_id)

        # Group by detail_type
        grouped = {}
        for detail_type, group in groupby(details, key=attrgetter("detail_type")):
            grouped[detail_type] = list(group)

        cache.set(cache_key, grouped, ProductDetailService.CACHE_TIMEOUT)

        duration = (time.time() - start_time) * 1000
        logger.info(f"Grouped details for product {product_id} in {duration:.2f}ms")

        return grouped

    @staticmethod
    def get_highlighted_details(product_id: int) -> List:
        """Get priority details for product summaries"""
        return ProductDetailService.get_product_details(
            product_id=product_id, highlighted_only=True
        )

    @staticmethod
    @transaction.atomic
    def bulk_create_details(
        product: Product, details_data: List[Dict]
    ) -> List[ProductDetail]:
        """Efficient bulk creation with validation"""
        start_time = time.time()

        details_to_create = []
        for data in details_data:
            detail = ProductDetail(
                product=product,
                template_id=data.get("template_id"),
                detail_type=data["detail_type"],
                label=data["label"],
                value=data["value"],
                unit=data.get("unit", ""),
                is_highlighted=data.get("is_highlighted", False),
                display_order=data.get("display_order", 0),
            )
            details_to_create.append(detail)

        created_details = ProductDetail.objects.bulk_create(details_to_create)

        # Invalidate cache
        CacheManager.invalidate("product_detail", product_id=product.id)

        duration = (time.time() - start_time) * 1000
        logger.info(f"Bulk created {len(created_details)} details in {duration:.2f}ms")

        return created_details

    @staticmethod
    def update_detail(detail_id: int, **update_data) -> ProductDetail:
        """Update a single detail and invalidate cache"""
        detail = ProductDetail.objects.get(id=detail_id)

        for field, value in update_data.items():
            setattr(detail, field, value)

        detail.save()

        # Invalidate cache
        CacheManager.invalidate("product_detail", product_id=detail.product_id)

        return detail

    @staticmethod
    def delete_detail(detail_id: int) -> bool:
        """Soft delete a detail"""
        try:
            detail = ProductDetail.objects.get(id=detail_id)
            detail.is_active = False
            detail.save()

            # Invalidate cache
            CacheManager.invalidate("product_detail", product_id=detail.product_id)

            return True
        except ProductDetail.DoesNotExist:
            return False

    @staticmethod
    def get_templates_for_category(category_id: int = None) -> QuerySet:
        """Get available templates for a category"""
        if category_id:
            return ProductDetailTemplate.objects.filter(
                models.Q(category_id=category_id) | models.Q(category__isnull=True)
            ).order_by("display_order", "label")
        return ProductDetailTemplate.objects.filter(category__isnull=True).order_by(
            "display_order", "label"
        )

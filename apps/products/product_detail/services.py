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
        print(
            f"Fetching details for product {product_id} with type {detail_type} and highlighted_only={highlighted_only}"
        )
        start_time = time.time()
        if CacheManager.cache_exists("product_detail", "list", product_id=product_id):
            cache_key = CacheKeyManager.make_key(
                "product_detail", "list", product_id=product_id
            )
            cached_data = cache.get(cache_key)
            if cached_data:
                duration = (time.time() - start_time) * 1000
                logger.info(
                    f"Cache hit for product {product_id} details in {duration:.2f}ms"
                )
                return cached_data
        print(f"Cache miss for product {product_id} details, querying database")
        queryset = ProductDetail.objects.select_related("product", "template").filter(
            product_id=product_id, is_active=True
        )

        if detail_type:
            queryset = queryset.filter(detail_type=detail_type)

        if highlighted_only:
            queryset = queryset.filter(is_highlighted=True)

        result = list(queryset.order_by("display_order", "label"))
        cache_key = CacheKeyManager.make_key(
            "product_detail", "list", product_id=product_id
        )
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
        if CacheManager.cache_exists(
            "product_detail", "grouped", product_id=product_id
        ):

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

        cache_key = CacheKeyManager.make_key(
            "product_detail", "grouped", product_id=product_id
        )
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
        CacheManager.invalidate_key(
            "product_detail", "list", product_id=detail.product_id
        )
        CacheManager.invalidate_key(
            "product_base", "detail_by_shortcode", short_code=detail.product_short_code
        )

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
        CacheManager.invalidate_key(
            "product_detail", "list", product_id=detail.product_id
        )
        CacheManager.invalidate_key(
            "product_base", "detail_by_shortcode", short_code=detail.product_short_code
        )

        return detail

    @staticmethod
    def delete_detail(detail_id: int) -> bool:
        """Soft delete a detail"""
        try:
            detail = ProductDetail.objects.get(id=detail_id)
            detail.is_active = False
            detail.save()

            # Invalidate cache
            CacheManager.invalidate_key(
                "product_detail", "list", product_id=detail.product_id
            )
            CacheManager.invalidate_key(
                "product_base",
                "detail_by_shortcode",
                short_code=detail.product_short_code,
            )

            return True
        except ProductDetail.DoesNotExist:
            return False

    @staticmethod
    def create_from_template(product, template, value, **kwargs):
        """Create a ProductDetail from a template"""
        detail_data = {
            "product": product,
            "template": template,
            "label": template.label,
            "detail_type": template.detail_type,
            "unit": template.unit,
            "display_order": template.display_order,
            "value": value,
            "created_from_template": True,
            **kwargs,
        }

        detail = ProductDetail(**detail_data)
        detail.full_clean()  # Validate before saving
        detail.save()
        CacheManager.invalidate_key("product_detail", "list", product_id=product.id)
        CacheManager.invalidate_key(
            "product_base", "detail_by_shortcode", short_code=product.short_code
        )
        return detail

    @staticmethod
    def create_template(template_data: Dict) -> ProductDetailTemplate:
        """Create a new template with validation"""
        start_time = time.time()

        # Business rule: Check for duplicate templates
        label = template_data["label"]
        category = template_data.get("category")
        detail_type = template_data["detail_type"]

        if ProductDetailTemplate.objects.filter(
            label=label, category=category, detail_type=detail_type
        ).exists():
            raise ValueError(
                "Template with this label, category, and detail type already exists"
            )

        template = ProductDetailTemplate.objects.create(**template_data)

        # Invalidate cache
        if template.category:
            CacheManager.invalidate_key(
                "product_detail", "category", category_id=template.category.id
            )

        duration = (time.time() - start_time) * 1000
        logger.info(f"Created template '{template.label}' in {duration:.2f}ms")

        return template

    @staticmethod
    def update_template(template_id: int, **update_data) -> ProductDetailTemplate:
        """Update a template with business rule validation"""
        template = ProductDetailTemplate.objects.get(id=template_id)

        # Business rule: If changing core identifiers, check for duplicates
        if any(field in update_data for field in ["label", "category", "detail_type"]):
            label = update_data.get("label", template.label)
            category = update_data.get("category", template.category)
            detail_type = update_data.get("detail_type", template.detail_type)

            if (
                ProductDetailTemplate.objects.filter(
                    label=label, category=category, detail_type=detail_type
                )
                .exclude(id=template_id)
                .exists()
            ):
                raise ValueError("Template with this combination already exists")

        for field, value in update_data.items():
            setattr(template, field, value)

        template.save()

        # Invalidate cache
        if template.category:
            CacheManager.invalidate_key(
                "product_detail", "category", category_id=template.category.id
            )

        return template

    @staticmethod
    def delete_template(template_id: int) -> bool:
        """Delete a template with business rule checks"""
        try:
            template = ProductDetailTemplate.objects.get(id=template_id)

            # Business rule: Cannot delete template if in use
            if template.product_details.filter(is_active=True).exists():
                return False

            # Cache category before deletion
            category = template.category
            template.delete()

            # Invalidate cache
            if category:
                CacheManager.invalidate_key(
                    "product_detail", "category", category_id=category.id
                )

            return True
        except ProductDetailTemplate.DoesNotExist:
            return False

    @staticmethod
    def bulk_create_templates(
        templates_data: List[Dict],
    ) -> List[ProductDetailTemplate]:
        """Bulk create templates with validation"""
        start_time = time.time()

        # Validate all templates first
        validated_templates = []
        seen_combinations = set()

        for template_data in templates_data:
            # Check for duplicates within the batch
            combo = (
                template_data["label"],
                template_data.get("category"),
                template_data["detail_type"],
            )

            if combo in seen_combinations:
                raise ValueError(
                    f"Duplicate template in batch: {template_data['label']}"
                )

            # Check against existing templates
            if ProductDetailTemplate.objects.filter(
                label=template_data["label"],
                category=template_data.get("category"),
                detail_type=template_data["detail_type"],
            ).exists():
                raise ValueError(f"Template already exists: {template_data['label']}")

            seen_combinations.add(combo)
            validated_templates.append(template_data)

        # Create all templates
        created_templates = []
        for template_data in validated_templates:
            template = ProductDetailTemplate.objects.create(**template_data)
            created_templates.append(template)

        # Invalidate caches for affected categories
        categories = set(t.category for t in created_templates if t.category)
        for category in categories:
            CacheManager.invalidate_key(
                "product_detail", "category", category_id=category.id
            )

        duration = (time.time() - start_time) * 1000
        logger.info(
            f"Bulk created {len(created_templates)} templates in {duration:.2f}ms"
        )

        return created_templates

    @staticmethod
    def get_templates_for_category(category_id: int = None) -> QuerySet:
        """Get available templates for a category with caching"""
        if CacheManager.cache_exists(
            "product_detail", "category", category_id=category_id
        ):
            cache_key = CacheKeyManager.make_key(
                "product_detail", "category", category_id=category_id
            )
            print(f"cache key: {cache_key}")
            cached_data = cache.get(cache_key)
            if cached_data:
                return cached_data
        if category_id:
            templates = ProductDetailTemplate.objects.filter(
                models.Q(category_id=category_id) | models.Q(category__isnull=True)
            ).order_by("display_order", "label")
        else:
            templates = ProductDetailTemplate.objects.filter(
                category__isnull=True
            ).order_by("display_order", "label")

        result = list(templates)

        cache_key = CacheKeyManager.make_key(
            "product_detail", "category", category_id=category_id
        )
        cache.set(cache_key, result, ProductDetailService.CACHE_TIMEOUT)

        return result

    @staticmethod
    def validate_template_usage(template_id: int) -> Dict:
        """Check how a template is being used (for admin insights)"""
        template = ProductDetailTemplate.objects.get(id=template_id)

        active_usage = template.product_details.filter(is_active=True).count()
        total_usage = template.product_details.count()

        return {
            "template_id": template_id,
            "active_usage_count": active_usage,
            "total_usage_count": total_usage,
            "can_delete": active_usage == 0,
            "products_using": list(
                template.product_details.filter(is_active=True)
                .values_list("product__id", flat=True)
                .distinct()
            ),
        }

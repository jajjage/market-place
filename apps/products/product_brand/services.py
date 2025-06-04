from django.core.cache import cache
from django.db import transaction
from django.db import models
from typing import List, Dict
import logging

from apps.products.product_brand.models import (
    Brand,
    BrandRequest,
    BrandVariant,
    BrandVariantTemplate,
)
from apps.products.product_brand.tasks import (
    notify_brand_request_approved,
    notify_brand_request_rejected,
    update_brand_stats,
)

logger = logging.getLogger(__name__)


class BrandService:
    """Service layer for brand operations"""

    @staticmethod
    def get_featured_brands(limit: int = 10) -> List[Brand]:
        """Get featured brands with caching"""
        cache_key = f"brands:featured:{limit}"
        brands = cache.get(cache_key)

        if brands is None:
            brands = list(
                Brand.objects.featured().with_stats().select_related()[:limit]
            )
            cache.set(cache_key, brands, timeout=1800)  # 30 minutes

        return brands

    @staticmethod
    def search_brands(query: str, filters: Dict = None) -> models.QuerySet:
        """Advanced brand search with filters"""
        queryset = Brand.objects.active().search(query)

        if filters:
            if filters.get("country"):
                queryset = queryset.filter(country_of_origin=filters["country"])
            if filters.get("verified_only"):
                queryset = queryset.filter(is_verified=True)
            if filters.get("min_products"):
                queryset = queryset.filter(
                    cached_product_count__gte=filters["min_products"]
                )
            if filters.get("min_rating"):
                queryset = queryset.filter(
                    cached_average_rating__gte=filters["min_rating"]
                )

        return queryset.with_stats()

    @staticmethod
    def create_brand_from_request(brand_request: "BrandRequest") -> Brand:
        """Create a brand from an approved request"""
        with transaction.atomic():
            brand = Brand.objects.create(
                name=brand_request.brand_name,
                website=brand_request.website,
                is_active=True,
            )

            brand_request.created_brand = brand
            brand_request.status = BrandRequest.Status.APPROVED
            brand_request.save()

            # Trigger async stats calculation
            update_brand_stats.delay(brand.id)

            return brand

    @staticmethod
    def get_brand_analytics(brand_id: int, days: int = 30) -> Dict:
        """Get brand analytics data"""
        cache_key = f"brand:{brand_id}:analytics:{days}"
        analytics = cache.get(cache_key)

        if analytics is None:
            # This would typically involve complex queries
            # Better to move to a separate analytics service
            # analytics = BrandAnalyticsService.calculate_analytics(brand_id, days)
            cache.set(cache_key, analytics, timeout=3600)

        return analytics


class BrandRequestService:
    """Service for handling brand requests"""

    @staticmethod
    def submit_request(
        user, brand_name: str, reason: str, website: str = ""
    ) -> "BrandRequest":
        """Submit a new brand request"""
        # Check for duplicates
        existing = BrandRequest.objects.filter(
            brand_name__iexact=brand_name, status=BrandRequest.Status.PENDING
        ).exists()

        if existing:
            raise ValueError("A request for this brand is already pending")

        # Check if brand already exists
        if Brand.objects.filter(name__iexact=brand_name).exists():
            raise ValueError("This brand already exists")

        return BrandRequest.objects.create(
            requested_by=user, brand_name=brand_name, reason=reason, website=website
        )

    @staticmethod
    def process_request(
        request_id: int, admin_user, action: str, notes: str = ""
    ) -> "BrandRequest":
        """Process a brand request (approve/reject)"""
        request_obj = BrandRequest.objects.get(id=request_id)

        with transaction.atomic():
            request_obj.processed_by = admin_user
            request_obj.admin_notes = notes

            if action == "approve":
                brand = BrandService.create_brand_from_request(request_obj)
                # Send notification to user
                notify_brand_request_approved.delay(request_obj.id, brand.id)
            else:
                request_obj.status = BrandRequest.Status.REJECTED
                notify_brand_request_rejected.delay(request_obj.id)

            request_obj.save()
            return request_obj


class BrandVariantService:
    """Service for managing brand variants"""

    @staticmethod
    def create_variant(
        brand_id: int, variant_data: dict, created_by=None
    ) -> BrandVariant:
        """Create a new brand variant"""
        brand = Brand.objects.get(id=brand_id)

        # Check if variant already exists
        existing = BrandVariant.objects.filter(
            brand=brand,
            language_code=variant_data["language_code"],
            region_code=variant_data.get("region_code", ""),
        ).exists()

        if existing:
            raise ValueError("Variant for this locale already exists")

        # Apply translations if available
        variant_data = BrandVariantService._apply_translations(brand, variant_data)

        return BrandVariant.objects.create(
            brand=brand, created_by=created_by, **variant_data
        )

    @staticmethod
    def _apply_translations(brand: Brand, variant_data: dict) -> dict:
        """Apply automatic translations based on templates"""
        template = BrandVariantTemplate.objects.filter(
            language_code=variant_data["language_code"],
            region_code=variant_data.get("region_code", ""),
            is_active=True,
        ).first()

        if template and template.name_translations:
            # Check if brand name has a known translation
            original_name = brand.name.lower()
            for original, translated in template.name_translations.items():
                if original.lower() == original_name:
                    variant_data["name"] = translated
                    break
            else:
                # No translation found, use original name
                variant_data.setdefault("name", brand.name)

        return variant_data

    @staticmethod
    def auto_generate_variants(brand_id: int) -> List[BrandVariant]:
        """Auto-generate variants based on templates and brand criteria"""
        brand = Brand.objects.get(id=brand_id)
        created_variants = []

        # Get applicable templates
        templates = BrandVariantTemplate.objects.filter(
            auto_generate_for_brands=True, is_active=True
        )

        for template in templates:
            # Check if brand meets criteria
            if BrandVariantService._meets_criteria(brand, template.brand_criteria):
                # Check if variant doesn't already exist
                exists = BrandVariant.objects.filter(
                    brand=brand,
                    language_code=template.language_code,
                    region_code=template.region_code,
                ).exists()

                if not exists:
                    variant_data = {
                        "language_code": template.language_code,
                        "region_code": template.region_code,
                        "name": brand.name,  # Will be translated by _apply_translations
                        "description": brand.description,
                        "is_auto_generated": True,
                        **template.default_settings,
                    }

                    variant = BrandVariantService.create_variant(brand_id, variant_data)
                    created_variants.append(variant)

        return created_variants

    @staticmethod
    def _meets_criteria(brand: Brand, criteria: dict) -> bool:
        """Check if brand meets template criteria"""
        if not criteria:
            return True

        if "min_products" in criteria:
            if brand.cached_product_count < criteria["min_products"]:
                return False

        if "min_rating" in criteria:
            if brand.cached_average_rating < criteria["min_rating"]:
                return False

        if "countries" in criteria:
            if brand.country_of_origin not in criteria["countries"]:
                return False

        return True

    @staticmethod
    def get_variant_for_locale(
        brand_id: int, language_code: str, region_code: str = ""
    ) -> BrandVariant:
        """Get the best variant for a specific locale"""
        brand = Brand.objects.get(id=brand_id)

        # Try exact match first
        variant = BrandVariant.objects.filter(
            brand=brand,
            language_code=language_code,
            region_code=region_code,
            is_active=True,
        ).first()

        if variant:
            return variant

        # Try language-only match
        variant = BrandVariant.objects.filter(
            brand=brand, language_code=language_code, region_code="", is_active=True
        ).first()

        if variant:
            return variant

        # Auto-generate if templates exist
        variants = BrandVariantService.auto_generate_variants(brand_id)
        for variant in variants:
            if (
                variant.language_code == language_code
                and variant.region_code == region_code
            ):
                return variant

        # Return None if no suitable variant found
        return None

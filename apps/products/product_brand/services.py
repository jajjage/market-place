from django.core.cache import cache
from django.db import transaction
from django.db import models
from typing import Any, List, Dict
import logging

from apps.products.product_brand.models import (
    Brand,
    BrandRequest,
    BrandVariant,
    BrandVariantTemplate,
)
from .tasks import bulk_generate_variants_for_template
from apps.notifications.services.notification_service import NotificationService
from apps.products.product_brand.tasks import (
    update_brand_stats,
)
from apps.core.utils.cache_manager import CacheManager
from apps.core.utils.cache_key_manager import CacheKeyManager
from apps.products.product_brand.utils.brand_variants import (
    brand_meets_criteria,
    create_variant_from_template,
)

logger = logging.getLogger("brands_performance")


class BrandService:
    """Service layer for brand operations"""

    @staticmethod
    def get_featured_brands(limit: int = 10) -> List[Brand]:
        """Get featured brands with caching"""
        # Fixed: Use proper cache key construction
        cache_key = CacheKeyManager.make_key("brand", "featured", limit=limit)
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

            # Comprehensive cache invalidation
            # This will invalidate ALL brand-related cache keys using wildcard patterns
            CacheManager.invalidate("brand")

            # Or be more specific if you want:
            # CacheManager.invalidate_pattern("brand", "featured")  # only featured brands
            # CacheManager.invalidate_pattern("brand", "list")      # only brand lists

            # Trigger async stats calculation
            update_brand_stats.delay(brand.id)

            return brand

    @staticmethod
    def get_brand_analytics(brand_id: int, days: int = 30) -> Dict:
        """Get brand analytics data"""
        # Fixed: Now uses proper analytics key template
        cache_key = CacheKeyManager.make_key(
            "brand", "analytics", brand_id=brand_id, days=days
        )
        analytics = cache.get(cache_key)

        if analytics is None:
            # This would typically involve complex queries
            analytics = {}  # Placeholder for actual analytics calculation
            cache.set(cache_key, analytics, timeout=3600)

        return analytics

    @staticmethod
    def get_brand_detail(brand_id: int) -> "Brand":
        """Get brand detail with enhanced cache management"""
        # Check if cache exists first
        if CacheManager.cache_exists("brand", "detail", id=brand_id):
            cache_key = CacheKeyManager.make_key("brand", "detail", id=brand_id)
            return cache.get(cache_key)

        # Fetch from database and cache
        from apps.products.product_brand.models import Brand

        brand = Brand.objects.with_stats().get(id=brand_id)

        cache_key = CacheKeyManager.make_key("brand", "detail", id=brand_id)
        cache.set(cache_key, brand, timeout=1800)

        return brand

    @staticmethod
    @transaction.atomic
    def update_brand(brand_id: int, **update_data):
        """Update brand and invalidate related caches"""
        from apps.products.product_brand.models import Brand

        # Ensure brand exists first
        if not Brand.objects.filter(id=brand_id).exists():
            raise Brand.DoesNotExist(f"Brand {brand_id} not found")

        # Update the brand
        updated_count = Brand.objects.filter(id=brand_id).update(**update_data)

        if updated_count > 0:
            BrandService.invalidate_brand_cache(brand_id)
        return updated_count

    @staticmethod
    def get_brand_stats(brand_id: int) -> Dict:
        """Get brand stats with caching"""
        cache_key = CacheKeyManager.make_key("brand", "stats", id=brand_id)
        stats = cache.get(cache_key)

        if stats is None:
            # Calculate stats
            stats = {}  # Placeholder for actual stats calculation
            cache.set(cache_key, stats, timeout=3600)

        return stats

    @staticmethod
    def invalidate_brand_cache(brand_id: int = None):
        """Invalidate brand-related cache"""
        if brand_id:
            # Invalidate specific brand caches
            def invalidate_caches():
                CacheManager.invalidate_key("brand", "detail", id=brand_id)
                CacheManager.invalidate_key("brand", "stats", id=brand_id)
                CacheManager.invalidate_pattern("brand", "variants_all", id=brand_id)
                CacheManager.invalidate_pattern("brand", "featured")
                CacheManager.invalidate_pattern("brand", "list")
                CacheManager.invalidate_pattern(
                    "brand", "all_analytics"
                )  # All analytics since they might be affected

            transaction.on_commit(invalidate_caches)
        else:
            # Invalidate all brand caches
            CacheManager.invalidate("brand")

    @staticmethod
    def get_cache_diagnostics() -> Dict[str, Any]:
        """Get cache diagnostics for monitoring"""
        return {
            "brand_cache_stats": CacheManager.get_cache_stats("brand"),
            "brand_variant_cache_stats": CacheManager.get_cache_stats("brand_variant"),
            "available_templates": {
                "brand": CacheKeyManager.get_available_templates("brand"),
                "brand_variant": CacheKeyManager.get_available_templates(
                    "brand_variant"
                ),
            },
        }


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
                context = {"brand_name": brand.name}
                NotificationService.send_notification(
                    request_obj.requested_by, "brand_request_approved", context
                )
            else:
                request_obj.status = BrandRequest.Status.REJECTED
                context = {"brand_name": request_obj.brand_name}
                NotificationService.send_notification(
                    request_obj.requested_by, "brand_request_rejected", context
                )

            request_obj.save()
            return request_obj


class BrandVariantService:
    """Service for managing brand variants"""

    @staticmethod
    @transaction.atomic
    def manual_generate_variants(
        brand_id: int, template_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Manually trigger variant generation for a specific brand

        Args:
            brand_id: ID of the brand
            template_ids: List of template IDs to use (if None, uses all eligible templates)

        Returns:
            Dict with generation results
        """
        try:
            brand = Brand.objects.get(id=brand_id, is_active=True)

            if template_ids:
                templates = BrandVariantTemplate.objects.filter(
                    id__in=template_ids, is_active=True
                )
            else:
                templates = BrandVariantTemplate.objects.filter(
                    is_active=True, auto_generate_for_brands=True
                )

            results = {
                "brand_id": brand_id,
                "brand_name": brand.name,
                "variants_created": [],
                "variants_skipped": [],
                "errors": [],
            }

            for template in templates:
                try:
                    if brand_meets_criteria(brand, template.brand_criteria):
                        existing_variant = BrandVariant.objects.filter(
                            brand=brand,
                            language_code=template.language_code,
                            region_code=template.region_code,
                        ).first()

                        if existing_variant:
                            results["variants_skipped"].append(
                                {
                                    "template_id": template.id,
                                    "reason": "Variant already exists",
                                }
                            )
                            continue

                        variant = create_variant_from_template(brand, template)
                        results["variants_created"].append(
                            {
                                "variant_id": variant.id,
                                "template_id": template.id,
                                "variant_name": variant.name,
                            }
                        )

                except Exception as e:
                    results["errors"].append(
                        f"Error with template {template.name}: {str(e)}"
                    )
            CacheManager.invalidate_pattern("brand_variant", "all", brand_id=brand_id)

            return results

        except Brand.DoesNotExist:
            return {"error": f"Brand with id {brand_id} not found"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

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


class BrandVariantTemplateService:
    """Service class for BrandVariantTemplate business logic"""

    @staticmethod
    def create_template(template_data, created_by=None):
        """Create a new template with validation"""
        template = BrandVariantTemplate.objects.create(**template_data)
        return template

    @staticmethod
    def regenerate_variants_from_template(
        template_id: int, force: bool = False
    ) -> Dict[str, Any]:
        """
        Regenerate all variants for a specific template

        Args:
            template_id: ID of the template
            force: If True, recreate existing variants

        Returns:
            Dict with regeneration results
        """
        try:
            template = BrandVariantTemplate.objects.get(id=template_id, is_active=True)

            if force:
                # Delete existing variants created by this template
                BrandVariant.objects.filter(
                    template=template, is_auto_generated=True
                ).delete()

            # Get all brands that meet criteria
            brands = Brand.objects.filter(is_active=True)
            eligible_brands = [
                brand
                for brand in brands
                if brand_meets_criteria(brand, template.brand_criteria)
            ]

            # Use Celery task for bulk generation
            task_result = bulk_generate_variants_for_template.delay(
                template_id, [brand.id for brand in eligible_brands]
            )

            return {
                "template_id": template_id,
                "task_id": task_result.id,
                "eligible_brands_count": len(eligible_brands),
                "message": "Regeneration task started",
            }

        except BrandVariantTemplate.DoesNotExist:
            return {"error": f"Template with id {template_id} not found"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

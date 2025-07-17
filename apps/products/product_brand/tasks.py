from typing import Any, Dict, List
from celery import shared_task

from apps.core.tasks import BaseTaskWithRetry


import logging

from apps.products.product_brand.utils.brand_variants import (
    brand_meets_criteria,
    create_variant_from_template,
)

from django.db import transaction

from .models import Brand, BrandVariant, BrandVariantTemplate

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTaskWithRetry)
def update_brand_stats(self, brand_id: int):
    """Update brand statistics asynchronously"""
    from apps.products.product_brand.services import BrandService

    try:
        brand = Brand.objects.get(id=brand_id)
        stats = brand._calculate_stats()

        # Update materialized fields
        Brand.objects.filter(id=brand_id).update(
            cached_product_count=stats["product_count"],
            cached_average_rating=stats["average_rating"],
        )

        # Invalidate cache
        BrandService.invalidate_brand_cache(brand_id)

        logger.info(f"Updated stats for brand {brand.name}")

    except Brand.DoesNotExist:
        logger.error(f"Brand {brand_id} not found")
    except Exception as exc:
        logger.error(f"Error updating brand stats: {exc}")
        self.retry(countdown=60, exc=exc)


@shared_task(bind=True, base=BaseTaskWithRetry)
def bulk_update_brand_stats():
    """Update all brand stats - run daily"""
    brand_ids = Brand.objects.active().values_list("id", flat=True)

    for brand_id in brand_ids:
        update_brand_stats.delay(brand_id.id)


@shared_task(bind=True, base=BaseTaskWithRetry)
def sync_variant_data_with_parent():
    """Sync variant data with parent brand when parent is updated"""
    # This would sync basic information from parent brand to variants
    # when the parent brand is updated
    pass


@shared_task(bind=True, base=BaseTaskWithRetry)
def auto_generate_brand_variants(self, brand_id: int) -> Dict[str, Any]:
    """
    Auto-generate brand variants based on active templates

    Args:
        brand_id: ID of the brand to generate variants for

    Returns:
        Dict with generation results
    """
    try:
        with transaction.atomic():
            brand = Brand.objects.select_for_update().get(id=brand_id, is_active=True)

            # Get all active templates with auto-generation enabled
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
                    # Check if brand meets template criteria
                    if brand_meets_criteria(brand, template.brand_criteria):
                        # Check if variant already exists
                        existing_variant = BrandVariant.objects.filter(
                            brand=brand,
                            language_code=template.language_code,
                            region_code=template.region_code,
                        ).first()

                        if existing_variant:
                            results["variants_skipped"].append(
                                {
                                    "template_id": template.id,
                                    "template_name": template.name,
                                    "reason": "Variant already exists",
                                }
                            )
                            continue

                        # Generate variant
                        variant = create_variant_from_template(brand, template)

                        results["variants_created"].append(
                            {
                                "variant_id": variant.id,
                                "template_id": template.id,
                                "template_name": template.name,
                                "variant_name": variant.name,
                                "locale": f"{variant.language_code}-{variant.region_code}",
                            }
                        )

                        logger.info(
                            f"Created variant {variant.id} for brand {brand.name} using template {template.name}"
                        )

                    else:
                        results["variants_skipped"].append(
                            {
                                "template_id": template.id,
                                "template_name": template.name,
                                "reason": "Brand does not meet criteria",
                            }
                        )

                except Exception as e:
                    error_msg = f"Error creating variant from template {template.name}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            return results

    except Brand.DoesNotExist:
        error_msg = f"Brand with id {brand_id} not found"
        logger.error(error_msg)
        return {"error": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error in auto_generate_brand_variants: {str(e)}"
        logger.error(error_msg)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))

        return {"error": error_msg}


@shared_task(bind=True, base=BaseTaskWithRetry)
def bulk_generate_variants_for_template(
    template_id: int, brand_ids: List[int] = None
) -> Dict[str, Any]:
    """
    Generate variants for multiple brands using a specific template

    Args:
        template_id: ID of the template to use
        brand_ids: List of brand IDs (if None, uses all eligible brands)

    Returns:
        Dict with generation results
    """
    try:
        with transaction.atomic():
            template = BrandVariantTemplate.objects.select_for_update().get(
                id=template_id, is_active=True
            )

            if brand_ids is None:
                # Get all brands that meet template criteria
                brands = Brand.objects.filter(is_active=True)
                eligible_brands = [
                    brand
                    for brand in brands
                    if brand_meets_criteria(brand, template.brand_criteria)
                ]
            else:
                eligible_brands = Brand.objects.filter(id__in=brand_ids, is_active=True)

            results = {
                "template_id": template_id,
                "template_name": template.name,
                "total_brands_processed": len(eligible_brands),
                "variants_created": [],
                "variants_skipped": [],
                "errors": [],
            }

            for brand in eligible_brands:
                try:
                    # Check if variant already exists
                    existing_variant = BrandVariant.objects.filter(
                        brand=brand,
                        language_code=template.language_code,
                        region_code=template.region_code,
                    ).first()

                    if existing_variant:
                        results["variants_skipped"].append(
                            {
                                "brand_id": brand.id,
                                "brand_name": brand.name,
                                "reason": "Variant already exists",
                            }
                        )
                        continue

                    # Generate variant
                    variant = create_variant_from_template(brand, template)

                    results["variants_created"].append(
                        {
                            "brand_id": brand.id,
                            "brand_name": brand.name,
                            "variant_id": variant.id,
                            "variant_name": variant.name,
                        }
                    )

                except Exception as e:
                    error_msg = (
                        f"Error creating variant for brand {brand.name}: {str(e)}"
                    )
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            return results

    except BrandVariantTemplate.DoesNotExist:
        error_msg = f"Template with id {template_id} not found"
        logger.error(error_msg)
        return {"error": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error in bulk_generate_variants_for_template: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

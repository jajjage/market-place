from celery import shared_task

from apps.core.tasks import BaseTaskWithRetry
from apps.products.product_brand.models import Brand

import logging


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
        update_brand_stats.delay(brand_.id)


@shared_task
def auto_generate_variants_for_new_brands():
    """Daily task to auto-generate variants for eligible brands"""
    from datetime import datetime, timedelta
    from apps.products.product_brand.services import BrandVariantService

    # Get brands created in the last day that don't have variants
    yesterday = datetime.now() - timedelta(days=1)

    new_brands = Brand.objects.filter(
        created_at__gte=yesterday, is_active=True
    ).exclude(variants__isnull=False)

    for brand in new_brands:
        try:
            variants = BrandVariantService.auto_generate_variants(brand.id)
            if variants:
                logger.info(
                    f"Auto-generated {len(variants)} variants for brand {brand.name}"
                )
        except Exception as e:
            logger.error(f"Error auto-generating variants for brand {brand.id}: {e}")


@shared_task
def sync_variant_data_with_parent():
    """Sync variant data with parent brand when parent is updated"""
    # This would sync basic information from parent brand to variants
    # when the parent brand is updated
    pass
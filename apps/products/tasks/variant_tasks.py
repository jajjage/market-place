# apps/products/tasks/variant_tasks.py

import logging
from celery import shared_task

from apps.products.services.variants_services import ProductVariantService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def create_product_variants_task(self, product_id: int, variant_combinations: list):
    """
    Celery task: call ProductVariantService.create_variants() and then update cache.
    `variant_combinations` is a list of dicts in the same format that bulk_create_variants expects.
    """
    try:
        # 1) Create the variants synchronously via service
        created_variants = ProductVariantService.create_variants(
            product_id, variant_combinations
        )

        # 2) Update the cache via service
        ProductVariantService.update_variant_cache(product_id)

        # Return a summary: IDs of created variants
        return {
            "product_id": product_id,
            "created_variant_ids": [v.id for v in created_variants],
            "total_created": len(created_variants),
        }

    except Exception as exc:
        logger.error(f"Error in create_product_variants_task({product_id}): {exc}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def update_product_variant_cache_task(self, product_id: int):
    """
    Celery task: call ProductVariantService.update_variant_cache().
    """
    try:
        ProductVariantService.update_variant_cache(product_id)
        return {"product_id": product_id, "status": "cache_updated"}
    except Exception as exc:
        logger.error(f"Error in update_product_variant_cache_task({product_id}): {exc}")
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task(bind=True, max_retries=3)
def generate_variant_combinations_task(
    self, product_id: int, variant_type_option_mapping: dict, base_price: float = None
):
    """
    Celery task: call ProductVariantService.generate_and_create_variants().
    """
    try:
        created_variants = ProductVariantService.generate_and_create_variants(
            product_id, variant_type_option_mapping, base_price
        )

        return {
            "product_id": product_id,
            "created_variant_ids": [v.id for v in created_variants],
            "total_created": len(created_variants),
        }
    except Exception as exc:
        logger.error(
            f"Error in generate_variant_combinations_task({product_id}): {exc}"
        )
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def bulk_create_product_variants_task(variant_payload: dict):
    """
    Celery task: expects a single dict of the form:
      {
        "product_id": <int>,
        "variant_combinations": [ {...}, {...}, … ]
      }
    Enqueues create_product_variants_task for that one product.
    Returns a small summary dict.
    """
    pid = variant_payload.get("product_id")
    combos = variant_payload.get("variant_combinations", [])
    try:
        async_res = create_product_variants_task.delay(pid, combos)
        return {"product_id": pid, "task_id": async_res.id, "status": "queued"}
    except Exception as exc:
        logger.error(
            f"Error in bulk_create_product_variants_task for product {pid}: {exc}"
        )
        return {"product_id": pid, "error": str(exc), "status": "failed"}

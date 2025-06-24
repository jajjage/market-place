from celery import shared_task
from decimal import Decimal
from typing import List, Dict
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger("performance_variant")


@shared_task(bind=True, max_retries=3)
def create_product_variants_task(
    self, product_id: int, variant_combinations: List[Dict]
):
    """
    Celery task to create product variants asynchronously.

    Args:
        product_id: ID of the product to create variants for
        variant_combinations: List of variant data dictionaries

    Returns:
        Dict with success/error information
    """
    try:
        from .services import ProductVariantService

        logger.info(f"Starting variant creation for product {product_id}")

        # Create variants
        created_variants = ProductVariantService.bulk_create_variants(
            product_id=product_id,
            variant_data=variant_combinations,
            validate_uniqueness=True,
            update_cache=True,
        )

        logger.info(
            f"Successfully created {len(created_variants)} variants for product {product_id}"
        )

        return {
            "success": True,
            "product_id": product_id,
            "created_count": len(created_variants),
            "variant_ids": [v.id for v in created_variants],
            "message": f"Successfully created {len(created_variants)} variants",
        }

    except ValidationError as e:
        logger.error(
            f"Validation error creating variants for product {product_id}: {str(e)}"
        )
        return {
            "success": False,
            "product_id": product_id,
            "error": str(e),
            "error_type": "validation_error",
        }

    except Exception as e:
        logger.error(
            f"Unexpected error creating variants for product {product_id}: {str(e)}"
        )

        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task, attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {
            "success": False,
            "product_id": product_id,
            "error": str(e),
            "error_type": "unexpected_error",
        }


@shared_task(bind=True, max_retries=3)
def update_product_variant_cache_task(self, product_id: int):
    """
    Celery task to update product variant cache asynchronously.

    Args:
        product_id: ID of the product to update cache for

    Returns:
        Dict with cache update results
    """
    try:
        from .services import ProductVariantService

        logger.info(f"Updating variant cache for product {product_id}")

        # Update cache
        stats = ProductVariantService.update_variant_cache(product_id)

        logger.info(f"Successfully updated cache for product {product_id}")

        return {
            "success": True,
            "product_id": product_id,
            "stats": stats,
            "message": "Cache updated successfully",
        }

    except Exception as e:
        logger.error(f"Error updating cache for product {product_id}: {str(e)}")

        # Retry on errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying cache update, attempt {self.request.retries + 1}")
            raise self.retry(countdown=30 * (self.request.retries + 1))

        return {"success": False, "product_id": product_id, "error": str(e)}


@shared_task(bind=True, max_retries=2)
def generate_variant_combinations_task(
    self,
    product_id: int,
    variant_type_options: Dict[int, List[int]],
    base_price: Decimal = None,
):
    """
    Celery task to generate variant combinations asynchronously.

    Args:
        product_id: ID of the product
        variant_type_options: Dict mapping variant type IDs to option ID lists
        base_price: Base price for calculations

    Returns:
        Dict with generated combinations or error info
    """
    try:
        from .services import ProductVariantService

        logger.info(f"Generating combinations for product {product_id}")

        # Generate combinations
        combinations = ProductVariantService.generate_all_combinations(
            product_id=product_id,
            variant_type_options=variant_type_options,
            base_price=base_price,
        )

        logger.info(
            f"Generated {len(combinations)} combinations for product {product_id}"
        )

        return {
            "success": True,
            "product_id": product_id,
            "combinations": combinations,
            "count": len(combinations),
            "message": f"Generated {len(combinations)} combinations",
        }

    except Exception as e:
        logger.error(
            f"Error generating combinations for product {product_id}: {str(e)}"
        )

        # Retry on errors
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying combination generation, attempt {self.request.retries + 1}"
            )
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {"success": False, "product_id": product_id, "error": str(e)}


@shared_task(bind=True, max_retries=2)
def generate_and_create_variants_task(
    self,
    product_id: int,
    variant_type_options: Dict[int, List[int]],
    base_price: Decimal = None,
    sku_separator: str = "-",
):
    """
    Celery task to generate and create all variant combinations asynchronously.

    Args:
        product_id: ID of the product
        variant_type_options: Dict mapping variant type IDs to option ID lists
        base_price: Base price for calculations
        sku_separator: Separator for SKU generation

    Returns:
        Dict with creation results
    """
    try:
        from .services import ProductVariantService

        logger.info(f"Generating and creating all variants for product {product_id}")

        # Generate and create variants
        created_variants = ProductVariantService.generate_and_create_variants(
            product_id=product_id,
            variant_type_options=variant_type_options,
            base_price=base_price,
            sku_separator=sku_separator,
        )

        logger.info(
            f"Successfully created {len(created_variants)} variants for product {product_id}"
        )

        return {
            "success": True,
            "product_id": product_id,
            "created_variants": [
                {
                    "id": v.id,
                    "sku": v.sku,
                    "price": str(v.price) if v.price else None,
                    "final_price": str(v.final_price) if v.final_price else None,
                }
                for v in created_variants
            ],
            "count": len(created_variants),
            "message": f"Successfully created {len(created_variants)} variants",
        }

    except ValidationError as e:
        logger.error(
            f"Validation error in generate_and_create for product {product_id}: {str(e)}"
        )
        return {
            "success": False,
            "product_id": product_id,
            "error": str(e),
            "error_type": "validation_error",
        }

    except Exception as e:
        logger.error(
            f"Unexpected error in generate_and_create for product {product_id}: {str(e)}"
        )

        # Retry on unexpected errors
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying generate_and_create, attempt {self.request.retries + 1}"
            )
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {
            "success": False,
            "product_id": product_id,
            "error": str(e),
            "error_type": "unexpected_error",
        }


@shared_task(bind=True, max_retries=3)
def bulk_stock_update_task(self, stock_updates: List[Dict]):
    """
    Celery task to perform bulk stock updates asynchronously.

    Args:
        stock_updates: List of stock update dictionaries

    Returns:
        Dict with update results
    """
    try:
        from .services import ProductVariantService

        logger.info(f"Starting bulk stock update for {len(stock_updates)} variants")

        # Perform bulk update
        results = ProductVariantService.bulk_update_stock(stock_updates)

        logger.info(
            f"Bulk stock update completed: {len(results['success'])} success, {len(results['errors'])} errors"
        )

        return {
            "success": True,
            "results": results,
            "message": f"Updated {len(results['success'])} variants, {len(results['errors'])} errors",
        }

    except Exception as e:
        logger.error(f"Error in bulk stock update: {str(e)}")

        # Retry on errors
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying bulk stock update, attempt {self.request.retries + 1}"
            )
            raise self.retry(countdown=30 * (self.request.retries + 1))

        return {"success": False, "error": str(e)}


@shared_task
def cleanup_variant_caches_task(older_than_hours: int = 24):
    """
    Celery task to cleanup old variant caches.

    Args:
        older_than_hours: Clean caches older than this many hours

    Returns:
        Dict with cleanup results
    """
    try:
        from apps.core.utils.cache_manager import CacheManager

        logger.info(
            f"Starting variant cache cleanup for entries older than {older_than_hours} hours"
        )

        # Clean up various cache patterns
        patterns = [
            "product_variants:*",
            "variant_matrix:*",
            "variant_by_options:*",
            "product_variant_stats:*",
            "product_variant_types:*",
        ]

        cleaned_count = 0
        for pattern in patterns:
            count = CacheManager.cleanup_pattern(pattern, older_than_hours)
            cleaned_count += count

        logger.info(f"Cleaned up {cleaned_count} cache entries")

        return {
            "success": True,
            "cleaned_count": cleaned_count,
            "message": f"Cleaned up {cleaned_count} cache entries",
        }

    except Exception as e:
        logger.error(f"Error in cache cleanup: {str(e)}")
        return {"success": False, "error": str(e)}


# Additional utility tasks


@shared_task(bind=True, max_retries=2)
def validate_product_variants_task(self, product_id: int):
    """
    Celery task to validate all variants for a product.

    Args:
        product_id: ID of the product to validate

    Returns:
        Dict with validation results
    """
    try:
        from .services import ProductVariantService
        from .models import ProductVariant

        logger.info(f"Validating variants for product {product_id}")

        variants = ProductVariant.objects.filter(
            product_id=product_id, is_active=True
        ).prefetch_related("options")

        validation_results = {
            "valid_variants": [],
            "invalid_variants": [],
            "warnings": [],
            "total_count": variants.count(),
        }

        for variant in variants:
            try:
                # Run full_clean to validate the variant
                variant.full_clean()

                # Additional business logic validation
                validation_result = ProductVariantService.validate_variant_combination(
                    product_id, list(variant.options.values_list("id", flat=True))
                )

                if validation_result["is_valid"]:
                    validation_results["valid_variants"].append(
                        {"id": variant.id, "sku": variant.sku}
                    )
                else:
                    validation_results["invalid_variants"].append(
                        {
                            "id": variant.id,
                            "sku": variant.sku,
                            "errors": validation_result["errors"],
                            "warnings": validation_result["warnings"],
                        }
                    )

            except ValidationError as e:
                validation_results["invalid_variants"].append(
                    {"id": variant.id, "sku": variant.sku, "errors": [str(e)]}
                )

        logger.info(
            f"Validation completed for product {product_id}: {len(validation_results['valid_variants'])} valid, {len(validation_results['invalid_variants'])} invalid"
        )

        return {
            "success": True,
            "product_id": product_id,
            "validation_results": validation_results,
        }

    except Exception as e:
        logger.error(f"Error validating variants for product {product_id}: {str(e)}")

        # Retry on errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying validation, attempt {self.request.retries + 1}")
            raise self.retry(countdown=30 * (self.request.retries + 1))

        return {"success": False, "product_id": product_id, "error": str(e)}

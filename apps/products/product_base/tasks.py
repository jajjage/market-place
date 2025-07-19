import logging
from django.db import transaction
from celery import shared_task
from apps.core.tasks import BaseTaskWithRetry
from apps.products.product_base.utils.description_utils import (
    extract_product_info_and_context,
    generate_fallback_description,
)

logger = logging.getLogger("products_performance")


@shared_task(bind=True, base=BaseTaskWithRetry)
def generate_seo_description_for_product(self, product_id, description_type="detailed"):
    """
    Generate SEO-optimized product description using Google GenAI.

    Args:
        product_id: ID of the product
        description_type: Type of description ('meta', 'short', 'detailed', 'marketing', 'technical', 'benefits')
    """
    try:
        from apps.products.product_base.models import Product
        from apps.products.product_base.utils.description_generator import (
            GoogleGenAISEODescriptionService,
        )

        # Get the product
        try:
            product = (
                Product.objects.select_related("brand", "category", "condition")
                .prefetch_related("product_details", "variants__options")
                .get(pk=product_id)
            )
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found")
            return {"error": f"Product {product_id} not found"}

        # Extract product information and context
        product_info, context_info = extract_product_info_and_context(product)

        # Initialize the GenAI service
        try:
            service = GoogleGenAISEODescriptionService()

            # Generate description using AI with product context
            description = service.generate_description(
                product_title=product.title,
                product_info=product_info,
                description_type=description_type,
                target_audience=context_info.get("target_audience"),
                tone=context_info.get("tone", "professional"),
                include_keywords=context_info.get("keywords", []),
                max_length=context_info.get("max_length"),
            )

            # If AI generation fails, use fallback method
            if not description or len(description.strip()) < 10:
                logger.warning(
                    f"AI description generation failed for product {product_id}, using fallback"
                )
                description = generate_fallback_description(
                    product, product_info, description_type
                )

        except Exception as e:
            logger.error(
                f"Error with GoogleGenAISEODescriptionService for product {product_id}: {str(e)}"
            )
            description = generate_fallback_description(
                product, product_info, description_type
            )

        # Ensure we have a valid description
        if not description or len(description.strip()) < 10:
            description = f"High-quality {product.title} available for purchase. Excellent condition and competitive pricing. Perfect for your needs."

        # Save to database based on description type
        with transaction.atomic():
            pd = Product.objects.select_for_update().get(id=product_id)

            if description_type == "short":
                pd.description = description
                update_fields = ["description"]
            else:  # detailed, marketing, technical, benefits
                pd.description = description
                update_fields = ["description"]

            pd.save(update_fields=update_fields)

            logger.info(
                f"SEO {description_type} description generated for product {product_id}: {len(description)} characters"
            )

        return {
            "success": True,
            "product_id": product_id,
            "description_type": description_type,
            "description_length": len(description),
            "description": (
                description[:100] + "..." if len(description) > 100 else description
            ),
        }

    except Exception as exc:
        logger.error(
            f"Error generating SEO description for product {product_id}: {str(exc)}"
        )
        return {"error": str(exc)}


@shared_task(bind=True, base=BaseTaskWithRetry)
def bump_product_cache_version(self):
    """
    Celery task to bump cache version asynchronously.
    """
    from apps.products.product_base.utils.cache_service import (
        ProductCacheVersionManager,
    )

    ProductCacheVersionManager.bump_version()


# @shared_task(bind=True, base=BaseTaskWithRetry)
# def generate_multiple_seo_descriptions_for_product(
#     self, product_id, description_types=None
# ):
#     """
#     Generate multiple types of SEO descriptions for a product.

#     Args:
#         product_id: ID of the product
#         description_types: List of description types to generate
#     """
#     if description_types is None:
#         description_types = ["meta", "short", "detailed"]

#     try:
#         from apps.products.product_metadata.models import ProductMeta
#         from apps.products.product_base.models import Product
#         from .utils.description_generator import (
#             GoogleGenAISEODescriptionService,
#         )

#         # Get the product
#         try:
#             product = Product.objects.get(pk=product_id).select_related(
#                 "brand", "category", "condition"
#             )
#         except Product.DoesNotExist:
#             logger.error(f"Product with ID {product_id} not found")
#             return {"error": f"Product {product_id} not found"}

#         # Extract product information and context
#         product_info, context_info = extract_product_info_and_context(product)

#         # Initialize the GenAI service
#         try:
#             service = GoogleGenAISEODescriptionService()

#             # Generate multiple descriptions
#             descriptions = service.generate_multiple_descriptions(
#                 product_title=product.title,
#                 product_info=product_info,
#                 description_types=description_types,
#                 target_audience=context_info.get("target_audience"),
#                 include_keywords=context_info.get("keywords", []),
#             )

#         except Exception as e:
#             logger.error(
#                 f"Error with GoogleGenAISEODescriptionService for product {product_id}: {str(e)}"
#             )
#             # Generate fallback descriptions
#             descriptions = {}
#             for desc_type in description_types:
#                 descriptions[desc_type] = generate_fallback_description(
#                     product, product_info, desc_type
#                 )

#         # Save to database
#         with transaction.atomic():
#             pd = Product.objects.select_for_update().get(id=product_id)
#             update_fields = []

#             for desc_type, description in descriptions.items():
#                 if desc_type == "meta":
#                     pd.seo_meta_description = description
#                     update_fields.append("seo_meta_description")
#                 elif desc_type == "short":
#                     pd.seo_short_description = description
#                     update_fields.append("seo_short_description")
#                 else:  # detailed, marketing, technical, benefits
#                     pd.description = description
#                     update_fields.append("seo_description")

#             pd.seo_generation_queued = True
#             update_fields.append("seo_generation_queued")
#             pd.save(update_fields=update_fields)

#             logger.info(
#                 f"Multiple SEO descriptions generated for product {product_id}: {len(descriptions)} types"
#             )

#         return {
#             "success": True,
#             "product_id": product_id,
#             "generated_types": list(descriptions.keys()),
#             "descriptions": {
#                 k: v[:100] + "..." if len(v) > 100 else v
#                 for k, v in descriptions.items()
#             },
#         }

#     except Exception as exc:
#         logger.error(
#             f"Error generating multiple SEO descriptions for product {product_id}: {str(exc)}"
#         )
#         return {"error": str(exc)}

import logging
from django.db import transaction
from celery import shared_task
from apps.core.tasks import BaseTaskWithRetry
from .utils.keywords_context import (
    extract_product_keywords_and_context,
    generate_fallback_keywords,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTaskWithRetry)
def generate_seo_keywords_for_product(self, product_id):
    """
    Generate SEO keywords for a product using Google GenAI.
    """
    try:
        from .models import ProductMeta
        from apps.products.product_base.models import Product
        from apps.products.product_metadata.utils.seo_generate import (
            GoogleGenAISEOKeywordService,
        )

        # Get the product
        try:
            product = Product.objects.get(pk=product_id).select_related(
                "brand", "category", "condition"
            )
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found")
            return {"error": f"Product {product_id} not found"}

        # Extract product information to build seed term and context
        seed_term, context_info = extract_product_keywords_and_context(product)

        if not seed_term:
            logger.warning(f"No seed term could be generated for product {product_id}")
            seed_term = "product"  # Fallback

        # Initialize the GenAI service
        try:
            service = GoogleGenAISEOKeywordService()

            # Generate keywords using AI with product context
            keywords = service.generate_keywords(
                seed_term=seed_term,
                count=25,  # Generate more keywords for better selection
                intent_filter="commercial",  # Focus on commercial intent for products
                target_audience=context_info.get("target_audience"),
                business_type="e-commerce",
            )

            # If AI generation fails, use fallback method
            if not keywords:
                logger.warning(
                    f"AI keyword generation failed for product {product_id}, using fallback"
                )
                keywords = generate_fallback_keywords(product, seed_term)

        except Exception as e:
            logger.error(
                f"Error with GoogleGenAISEOKeywordService for product {product_id}: {str(e)}"
            )
            keywords = generate_fallback_keywords(product, seed_term)

        # Ensure we have at least some keywords
        if not keywords:
            keywords = [
                f"buy {product.title}",
                f"best {product.title}",
                f"{product.title} for sale",
                f"{product.title} online",
                f"cheap {product.title}",
            ]

        # Save to database
        with transaction.atomic():
            pm = ProductMeta.objects.select_for_update().get(product_id=product_id)
            pm.seo_keywords = ", ".join(keywords[:50])  # Limit to 50 keywords
            pm.seo_generation_queued = True
            pm.save(update_fields=["seo_keywords", "seo_generation_queued"])

            logger.info(
                f"SEO keywords generated for product {product_id}: {len(keywords)} keywords"
            )

        return {
            "success": True,
            "product_id": product_id,
            "keywords_count": len(keywords),
            "seed_term": seed_term,
        }

    except Exception as exc:
        logger.error(
            f"Error generating SEO keywords for product {product_id}: {str(exc)}"
        )
        return {"error": str(exc)}

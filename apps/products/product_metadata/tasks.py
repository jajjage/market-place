# tasks.py
from celery import shared_task
import logging

from apps.core.tasks import BaseTaskWithRetry

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTaskWithRetry)
def generate_seo_keywords_for_product(self, product_id):
    """
    Generate SEO keywords for a product using local methods (no AI needed).
    """
    try:
        from .models import ProductMeta
        from apps.products.product_base.models import Product

        # Import whichever service you prefer:
        # Option 1: Full-featured local service
        from apps.products.product_metadata.utils.seo_generate import (
            LocalSEOKeywordService,
        )

        # Option 2: Simple service
        # from apps.products.product_metadata.utils.seo_generate import SimpleKeywordService

        # Option 3: Just the function
        # from apps.products.product_metadata.utils.seo_generate import generate_basic_seo_keywords

        # Get the product
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found")
            return {"error": f"Product {product_id} not found"}

        # Generate keywords using your chosen method

        # Method 1: Full-featured (recommended)
        svc = LocalSEOKeywordService()
        keywords = svc.generate_keywords(product.title, count=12)

        # Method 2: Simple class
        # svc = SimpleKeywordService()
        # keywords = svc.generate_keywords(product.title, count=12)

        # Method 3: Just function (simplest)
        # keywords = generate_basic_seo_keywords(product.title, count=12)

        if not keywords:
            # Fallback to basic keywords if everything fails
            keywords = [
                f"buy {product.title}",
                f"best {product.title}",
                f"{product.title} for sale",
                f"{product.title} online",
                f"cheap {product.title}",
            ]
        pm = ProductMeta.objects.select_for_update().get(product_id=product_id)
        # … generate the keywords …
        pm.seo_keywords = ", ".join(keywords)
        pm.seo_generation_queued = False
        pm.save(update_fields=["seo_keywords", "seo_generation_queued"])

        logger.info(f"SEO keywords for product {product_id}: {len(keywords)} keywords")

    except Exception as exc:
        logger.error(
            f"Error generating SEO keywords for product {product_id}: {str(exc)}"
        )

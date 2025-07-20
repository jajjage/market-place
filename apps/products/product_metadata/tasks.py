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
    """Generate SEO keywords for a product using Google GenAI."""
    try:
        from .models import ProductMeta
        from apps.products.product_base.models import Product
        from apps.products.product_metadata.utils.seo_generate import (
            GoogleGenAISEOKeywordService,
        )

        # Get the product first (outside transaction)
        try:
            product = Product.objects.select_related(
                "brand", "category", "condition"
            ).get(pk=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product with ID {product_id} not found")
            return {"error": f"Product {product_id} not found"}

        # Generate keywords (outside transaction to avoid long-running transaction)
        seed_term, context_info = extract_product_keywords_and_context(product)

        if not seed_term:
            logger.warning(f"No seed term could be generated for product {product_id}")
            seed_term = "product"

        # Generate keywords
        keywords = []
        try:
            service = GoogleGenAISEOKeywordService()
            keywords = service.generate_keywords(
                seed_term=seed_term,
                count=25,
                intent_filter="commercial",
                target_audience=context_info.get("target_audience"),
                business_type="e-commerce",
            )
        except Exception as e:
            logger.error(
                f"Error with GoogleGenAISEOKeywordService for product {product_id}: {str(e)}"
            )

        # Fallback if needed
        if not keywords:
            keywords = generate_fallback_keywords(product, seed_term)

        if not keywords:
            keywords = [
                f"buy {product.title}",
                f"best {product.title}",
                f"{product.title} for sale",
                f"{product.title} online",
                f"cheap {product.title}",
            ]

        # Now save to database in a single atomic operation
        try:
            with transaction.atomic():
                pm, created = ProductMeta.objects.update_or_create(
                    product_id=product_id,
                    defaults={
                        "seo_keywords": keywords[:50],
                        "seo_generation_queued": False,  # Mark as completed
                    },
                )

                action = "created" if created else "updated"
                logger.info(
                    f"SEO keywords {action} for product {product_id}: {len(keywords)} keywords"
                )

        except Exception as db_error:
            logger.error(f"Database error for product {product_id}: {str(db_error)}")
            # Reset the queued flag so it can be retried
            try:
                ProductMeta.objects.filter(product_id=product_id).update(
                    seo_generation_queued=False
                )
            except Exception:
                pass  # If this fails, the task will retry anyway
            raise

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

        # Reset queued flag on error so task can be retried
        try:
            ProductMeta.objects.filter(product_id=product_id).update(
                seo_generation_queued=False
            )
        except Exception:
            pass

        # Retry the task if we have retries left
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=60 * (2**self.request.retries)
            )  # Exponential backoff

        return {"error": str(exc)}

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from apps.core.tasks import BaseTaskWithRetry
from .models import SearchLog
from .documents import ProductDocument

# from .utils.product_search_utils import ProductSearchUtils

logger = logging.getLogger("product_search")


@shared_task(bind=True, base=BaseTaskWithRetry)
def update_popularity_scores():
    """Update popularity scores for all products"""
    try:
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.scan()  # Scan all documents

        updated_count = 0
        for hit in search:
            try:
                from apps.products.product_base.models import Product

                product = Product.objects.get(id=hit.meta.id)

                # Update the document with new popularity score
                doc = ProductDocument.get(id=hit.meta.id)
                new_score = doc.prepare_popularity_score(product)
                doc.update(popularity_score=new_score)

                updated_count += 1

                if updated_count % 100 == 0:
                    logger.info(
                        f"Updated popularity scores for {updated_count} products"
                    )

            except Exception as e:
                logger.error(
                    f"Error updating popularity score for product {hit.meta.id}: {str(e)}"
                )
                continue

        logger.info(
            f"Successfully updated popularity scores for {updated_count} products"
        )
        return updated_count

    except Exception as e:
        logger.error(f"Error in update_popularity_scores task: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def bulk_update_seo_keywords():
    """Bulk update SEO keywords for products"""
    try:

        from django.core.management import call_command

        # Call the management command
        call_command("update_product_seo_keywords")

        logger.info("Successfully updated SEO keywords and re-indexed products")

    except Exception as e:
        logger.error(f"Error in bulk_update_seo_keywords task: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def cleanup_search_logs(days_to_keep=30):
    """Clean up old search logs"""
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        deleted_count = SearchLog.objects.filter(created_at__lt=cutoff_date).delete()[0]

        logger.info(f"Cleaned up {deleted_count} old search log entries")
        return deleted_count

    except Exception as e:
        logger.error(f"Error in cleanup_search_logs task: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def index_product_async(product_id):
    """Async task to index a single product"""
    try:
        from apps.products.product_base.models import Product

        product = Product.objects.select_related(
            "seller", "category", "brand", "condition", "meta"
        ).get(id=product_id)

        # Index the product
        doc = ProductDocument()
        doc.meta.id = product.id
        doc.update(product)

        logger.info(f"Successfully indexed product {product_id}")

    except Product.DoesNotExist:
        logger.warning(f"Product {product_id} does not exist, skipping indexing")
    except Exception as e:
        logger.error(f"Error indexing product {product_id}: {str(e)}")
        raise


@shared_task(bind=True, base=BaseTaskWithRetry)
def remove_product_from_index_async(product_id):
    """Async task to remove a product from the index"""
    try:
        doc = ProductDocument.get(id=product_id)
        doc.delete()

        logger.info(f"Successfully removed product {product_id} from index")

    except Exception as e:
        logger.warning(f"Error removing product {product_id} from index: {str(e)}")
        # Don't raise exception as the product might not exist in the index

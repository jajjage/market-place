# apps/products/tasks/rating_tasks.py

import logging
import time

from celery import shared_task
from django.core.cache import cache

from apps.products.services.rating_services import ProductRatingService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def update_product_rating_aggregates_task(self, product_id: int):
    """
    Asynchronously update cached rating aggregates for a single product.
    Retries up to 3 times on failure, with exponential backoff.
    """
    try:
        ProductRatingService._update_rating_aggregates(product_id=product_id)
    except Exception as exc:
        logger.error(
            f"Error updating rating aggregates for product {product_id}: {exc}"
        )
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))


@shared_task
def bulk_update_rating_aggregates_task(product_ids: list):
    """
    Given a list of product IDs, queue an individual `update_product_rating_aggregates_task`
    for each one. Returns a list of “Queued…” or “Failed to queue…” strings.
    """
    results = []
    for pid in product_ids:
        try:
            update_product_rating_aggregates_task.delay(pid)
            results.append(f"Queued update for product {pid}")
        except Exception as e:
            results.append(f"Failed to queue product {pid}: {e}")
    return results


@shared_task(bind=True)
def debounced_rating_aggregate_update(
    self, product_id: int, debounce_seconds: int = 30
):
    """
    Debounced update: any number of calls within `debounce_seconds` for the same product_id
    will collapse into a single actual `update_product_rating_aggregates_task`.

    Implementation detail:
      1. On the “first invocation,” store a timestamp in Redis, then reschedule this
         same task to run after `debounce_seconds`. We pass a flag `_already_debounced=True`
         so that the second invocation (after countdown) knows it’s time to check.
      2. On the “second invocation,” compare the stored timestamp. If it has changed, skip.
         Otherwise, queue the real `update_product_rating_aggregates_task.delay(product_id)`.
    """
    cache_key = f"rating_update_debounce_{product_id}"
    now = int(time.time())
    cache.set(cache_key, now, timeout=debounce_seconds + 10)

    # If `_already_debounced` is not set, this is the “first pass”: schedule the second pass.
    if not getattr(self.request, "_already_debounced", False):
        return self.apply_async(
            (product_id, debounce_seconds),
            countdown=debounce_seconds,
            # Celery ignores unexpected kwargs, so we can tag this run as “second pass”:
            kwargs={"_already_debounced": True},
        )

    # If we reach here, `_already_debounced=True` means the countdown expired.
    latest = cache.get(cache_key)
    if latest != now:
        # A newer invocation (with a different timestamp) happened in the meantime → skip
        return f"Skipped update for product {product_id} — newer request exists"

    # We’re still the most recent request → do the actual update
    return update_product_rating_aggregates_task.delay(product_id)

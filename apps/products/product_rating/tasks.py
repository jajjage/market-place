# apps/products/tasks/rating_tasks.py

import logging
import time

from celery import shared_task
from django.core.cache import cache

from apps.core.tasks import BaseTaskWithRetry

from .services import ProductRatingService

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=BaseTaskWithRetry)
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


@shared_task(bind=True, base=BaseTaskWithRetry)
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


@shared_task(bind=True, base=BaseTaskWithRetry)
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

    # Check if this is the initial call or the delayed execution
    is_delayed_execution = getattr(self.request, "_already_debounced", False)

    if not is_delayed_execution:
        # FIRST INVOCATION: Set timestamp and schedule delayed execution
        cache.set(cache_key, now, timeout=debounce_seconds + 10)

        # Schedule the actual execution after debounce period
        return self.apply_async(
            (product_id, debounce_seconds),
            countdown=debounce_seconds,
            kwargs={"_already_debounced": True, "_scheduled_at": now},
        )

    # DELAYED EXECUTION: Check if we're still the latest request
    scheduled_at = getattr(self.request, "_scheduled_at", now)
    latest_timestamp = cache.get(cache_key)

    if latest_timestamp is None:
        # Cache expired, probably safe to skip
        return f"Skipped update for product {product_id} — cache expired"

    if latest_timestamp > scheduled_at:
        # A newer request came in after we were scheduled
        return f"Skipped update for product {product_id} — newer request exists"

    # We're still the latest request, proceed with update
    logger.info(f"Executing debounced rating update for product {product_id}")
    return update_product_rating_aggregates_task.delay(product_id)

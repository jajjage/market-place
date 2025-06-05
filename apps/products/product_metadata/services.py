# apps/products/services/product_meta.py

from datetime import timezone
from django.db import transaction, models
from django.db.models import Case, When
from django.core.cache import cache
from .models import ProductMeta
from apps.core.utils.cache_key_manager import CacheKeyManager


def increment_view_count(product_meta_id: int, use_cache_buffer: bool = True):
    """
    Safely increment the view counter for a given ProductMeta.

    - If use_cache_buffer=True, we increment a Redis‐buffered counter
      and flush to the DB only every N hits (to avoid DB write storms).
    - Otherwise, do a direct DB update.
    """
    cache_key = CacheKeyManager.make_key(
        "product_meta", "views_buffer", product_meta_id=product_meta_id
    )
    if use_cache_buffer:
        # Increment an in‐memory counter in Redis (atomic INCR)
        buffer_val = cache.incr(cache_key, delta=1)
        THRESHOLD = 10  # e.g., every 10 views, flush to DB
        if buffer_val >= THRESHOLD:
            # Flush to DB and reset buffer
            with transaction.atomic():
                pm = ProductMeta.objects.select_for_update().get(pk=product_meta_id)
                pm.views_count = models.F("views_count") + buffer_val
                pm.save(update_fields=["views_count", "updated_at"])
                cache.set(cache_key, 0, timeout=None)
    else:
        # Simpler: direct DB update
        ProductMeta.objects.filter(pk=product_meta_id).update(
            views_count=models.F("views_count") + 1, updated_at=timezone.now()
        )


def get_featured_products(limit: int = 20):
    """
    Return a queryset of featured ProductMeta, ordered by views_count desc.
    Caches the entire queryset (IDs) for 5 minutes to avoid repeated DB hits.
    """
    cache_key = CacheKeyManager.make_key("product_meta", "featured_ids", limit=limit)
    ids = cache.get(cache_key)
    if ids is None:
        qs = ProductMeta.objects.filter(featured=True).order_by("-views_count")
        ids = list(qs.values_list("pk", flat=True)[:limit])
        cache.set(cache_key, ids, timeout=300)
    # Return a fresh queryset that pulls the specific IDs to preserve ordering
    preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
    return ProductMeta.objects.filter(pk__in=ids).order_by(preserved)


def validate_seo_keywords_format(raw_value: str) -> str:
    """
    Apply the same logic you currently have in ProductMetaWriteSerializer.validate_seo_keywords.
    Raises ValueError on invalid format. Returns cleaned string.
    """
    if not raw_value:
        return ""
    # Remove extra spaces and split
    cleaned = " ".join(raw_value.split())
    keywords = [k.strip() for k in cleaned.split(",")]
    MAX_KEYWORD_LENGTH = 50
    for kw in keywords:
        if len(kw) > MAX_KEYWORD_LENGTH:
            raise ValueError(
                f"Individual keyword '{kw}' exceeds {MAX_KEYWORD_LENGTH} chars."
            )
    MAX_KEYWORDS = 10
    if len(keywords) > MAX_KEYWORDS:
        raise ValueError(f"Too many keywords; maximum allowed is {MAX_KEYWORDS}.")
    return cleaned

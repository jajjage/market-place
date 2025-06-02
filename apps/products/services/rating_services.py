# apps/products/services/rating_services.py

from django.conf import settings
from django_redis import get_redis_connection
from django.db import transaction
from django.core.cache import cache
from django.db.models import Avg, Count, Q

from typing import Dict, Optional

from apps.products.models import (
    ProductRating,
    ProductRatingAggregate,
    RatingHelpfulness,
)

CACHE_TTL = getattr(settings, "RATINGS_CACHE_TTL", 300)


class ProductRatingService:
    """Service for handling product rating operations"""

    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    @transaction.atomic
    def add_or_update_rating(
        product_id: int,
        user_id: int,
        rating: int,
        review: str = "",
        title: str = "",
        is_verified_purchase: bool = False,
    ) -> ProductRating:
        """
        Add a new rating or update an existing rating (same user + same product).
        Once saved, enqueue an asynchronous aggregate‐recalculation task and clear caches.
        """
        # 1) Create or update the ProductRating row
        rating_obj, created = ProductRating.objects.update_or_create(
            product_id=product_id,
            user_id=user_id,
            defaults={
                "rating": rating,
                "review": review,
                "title": title,
                "is_verified_purchase": is_verified_purchase,
                "is_approved": True,  # adjust this if you have approval flows
            },
        )

        # 2) Instead of recalculating aggregates synchronously, enqueue a Celery task
        ProductRatingService.trigger_rating_aggregate_update(product_id=product_id)

        # 3) Invalidate any per-product Ratings list cache
        redis = get_redis_connection("default")
        pattern = f"ratings:product_ratings:*:{product_id}"
        for key in redis.scan_iter(match=pattern):
            redis.delete(key)

        # 4) Invalidate the “rating_aggregate” cache key
        cache.delete(
            ProductRatingService.get_cache_key(
                "rating_aggregate", product_id=product_id
            )
        )

        return rating_obj

    @staticmethod
    def _update_rating_aggregates(product_id: int):
        """
        Recompute and upsert the ProductRatingAggregate row for `product_id`.
        This is called by the Celery task itself (not by the view).
        """
        ratings = ProductRating.objects.filter(product_id=product_id, is_approved=True)

        if not ratings.exists():
            # If no approved ratings yet, set defaults
            ProductRatingAggregate.objects.update_or_create(
                product_id=product_id,
                defaults={
                    "average_rating": 0,
                    "total_count": 0,
                    "verified_count": 0,
                    "stars_5_count": 0,
                    "stars_4_count": 0,
                    "stars_3_count": 0,
                    "stars_2_count": 0,
                    "stars_1_count": 0,
                    "has_reviews": False,
                    "last_rating_date": None,
                },
            )
            return

        # Aggregate all the statistics in one query
        stats = ratings.aggregate(
            avg_rating=Avg("rating"),
            total_count=Count("id"),
            verified_count=Count("id", filter=Q(is_verified_purchase=True)),
            stars_5=Count("id", filter=Q(rating=5)),
            stars_4=Count("id", filter=Q(rating=4)),
            stars_3=Count("id", filter=Q(rating=3)),
            stars_2=Count("id", filter=Q(rating=2)),
            stars_1=Count("id", filter=Q(rating=1)),
        )

        last_rating = ratings.order_by("-created_at").first()
        has_reviews = (
            ratings.exclude(review__isnull=True).exclude(review__exact="").exists()
        )

        ProductRatingAggregate.objects.update_or_create(
            product_id=product_id,
            defaults={
                "average_rating": round(stats["avg_rating"] or 0, 2),
                "total_count": stats["total_count"],
                "verified_count": stats["verified_count"],
                "stars_5_count": stats["stars_5"],
                "stars_4_count": stats["stars_4"],
                "stars_3_count": stats["stars_3"],
                "stars_2_count": stats["stars_2"],
                "stars_1_count": stats["stars_1"],
                "has_reviews": has_reviews,
                "last_rating_date": last_rating.created_at if last_rating else None,
            },
        )

    @staticmethod
    def get_cache_key(view_name: str, **kwargs) -> str:
        """
        Generate a cache key. We include only non-empty kwargs: page, per_page, product_id.
        Example: get_cache_key("rating_aggregate", product_id=42) -> "variants:rating_aggregate:42"
        """
        page = kwargs.get("page", "")
        per_page = kwargs.get("per_page", "")
        product_id = kwargs.get("product_id", "")

        key_parts = [str(part) for part in [page, per_page, product_id] if part != ""]
        key_suffix = ":".join(key_parts) if key_parts else "default"
        return f"variants:{view_name}:{key_suffix}"

    @staticmethod
    def delete_product_ratings_cache(product_id: int):
        """Delete any cached “product_ratings” entries for this product_id in Redis."""
        redis = get_redis_connection("default")
        pattern = f"ratings:product_ratings:*:{product_id}"
        for key in redis.scan_iter(match=pattern):
            redis.delete(key)

    @staticmethod
    def get_product_ratings(
        product_id: int,
        page: int = 1,
        per_page: int = 10,
        filter_rating: int = None,
        sort_by: str = "newest",
    ) -> Dict:
        """
        Return a paginated list of approved ratings for a product, with optional filter/sort.
        Caches the result for CACHE_TIMEOUT seconds.
        """
        cache_key = ProductRatingService.get_cache_key(
            "product_ratings", page=page, product_id=product_id, per_page=per_page
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        queryset = ProductRating.objects.filter(
            product_id=product_id, is_approved=True
        ).select_related("user")

        if filter_rating:
            queryset = queryset.filter(rating=filter_rating)

        if sort_by == "helpful":
            queryset = queryset.order_by("-helpful_count", "-created_at")
        elif sort_by == "verified":
            queryset = queryset.filter(is_verified_purchase=True).order_by(
                "-created_at"
            )
        elif sort_by == "oldest":
            queryset = queryset.order_by("created_at")
        else:  # “newest” by default
            queryset = queryset.order_by("-created_at")

        from django.core.paginator import Paginator

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)
        result = {
            "ratings": list(page_obj),
            "total_count": paginator.count,
            "current_page": page,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }

        cache.set(cache_key, result, ProductRatingService.CACHE_TIMEOUT)
        return result

    @staticmethod
    @transaction.atomic
    def vote_helpfulness(rating_id: int, user_id: int, is_helpful: bool) -> bool:
        """
        Create or update a “helpful” vote on a rating, and update that rating’s helpful_count/total_votes.
        Returns True if a new vote was created, False if an existing vote was updated.
        """
        vote, created = RatingHelpfulness.objects.update_or_create(
            rating_id=rating_id, user_id=user_id, defaults={"is_helpful": is_helpful}
        )

        rating = ProductRating.objects.get(id=rating_id)
        helpful_votes = RatingHelpfulness.objects.filter(
            rating_id=rating_id, is_helpful=True
        ).count()
        total_votes = RatingHelpfulness.objects.filter(rating_id=rating_id).count()

        rating.helpful_count = helpful_votes
        rating.total_votes = total_votes
        rating.save(update_fields=["helpful_count", "total_votes"])

        return created

    @staticmethod
    def get_rating_aggregate(product_id: int) -> Optional[ProductRatingAggregate]:
        """
        Fetch the cached ProductRatingAggregate for a product.
        If not in cache, load from the database (or create it if missing), then cache it.
        """
        cache_key = ProductRatingService.get_cache_key(
            "rating_aggregate", product_id=product_id
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            aggregate = ProductRatingAggregate.objects.get(product_id=product_id)
            cache.set(cache_key, aggregate, ProductRatingService.CACHE_TIMEOUT)
            return aggregate
        except ProductRatingAggregate.DoesNotExist:
            # If no aggregate exists yet, force‐recompute (synchronously) so that next call has data
            ProductRatingService._update_rating_aggregates(product_id)
            return ProductRatingAggregate.objects.get(product_id=product_id)

    # ────────────────────────────────────────────────────
    # CELERY TASK-ENQUEUE “TRIGGERS” (lazy imports to avoid circular import)
    # ────────────────────────────────────────────────────

    @staticmethod
    def trigger_rating_aggregate_update(product_id: int, delay_seconds: int = 0):
        """
        Enqueue (or schedule) the debounced Celery task to recalc aggregates for one product.
        If delay_seconds > 0, schedule it in the future; otherwise queue immediately.
        """
        from apps.products.tasks.rating_tasks import debounced_rating_aggregate_update

        if delay_seconds > 0:
            return debounced_rating_aggregate_update.apply_async(
                args=[product_id], countdown=delay_seconds
            )
        else:
            return debounced_rating_aggregate_update.delay(product_id)

    @staticmethod
    def trigger_bulk_rating_aggregate_update(product_ids: list):
        """
        Enqueue a bulk‐update Celery task that will queue individual updates internally.
        """
        from apps.products.tasks.rating_tasks import bulk_update_rating_aggregates_task

        return bulk_update_rating_aggregates_task.delay(product_ids)

    @staticmethod
    def schedule_rating_aggregate_update(product_id: int, eta_datetime=None):
        """
        Schedule a debounced update at an exact datetime (`eta_datetime` must be a timezone‐aware datetime).
        """
        from apps.products.tasks.rating_tasks import debounced_rating_aggregate_update

        return debounced_rating_aggregate_update.apply_async(
            args=[product_id], eta=eta_datetime
        )

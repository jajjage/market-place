import hashlib
import json
import logging
from django.conf import settings
from django_redis import get_redis_connection
from django.db import transaction
from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.utils import timezone

from typing import Dict, Optional, Tuple


from .models import (
    ProductRating,
    ProductRatingAggregate,
    RatingHelpfulness,
)
from apps.core.utils.cache_key_manager import CacheKeyManager

CACHE_TTL = getattr(settings, "RATINGS_CACHE_TTL", 300)

logger = logging.getLogger("ratings_performance")


class ProductRatingService:
    """Service for handling product rating operations"""

    CACHE_TIMEOUT = 3600  # 1 hour
    LIST_KEYS_SET = "safetrade:product_rating:list:keys"

    @staticmethod
    def can_user_rate_product(product_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Check if a user can rate a product based on:
        1. User must have completed a purchase (transaction) for this product
        2. User cannot be the seller of the product
        3. Transaction must be marked as completed
        4. User hasn't already rated this product (for new ratings)
        """
        from apps.transactions.models import EscrowTransaction  # Adjust import path
        from apps.products.product_base.models import Product

        # Adjust import path

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return False, "Product not found"

        # Check if user is the seller
        if product.seller_id == user_id:
            return False, "You cannot rate your own product"

        # Check if user has completed a purchase for this product
        completed_purchase = EscrowTransaction.objects.filter(
            product_id=product_id,
            buyer_id=user_id,
            status="completed",  # Adjust status field name as needed
        ).exists()

        if not completed_purchase:
            return False, "You can only rate products you have purchased and received"

        # For updates, we allow existing ratings to be modified
        existing_rating = ProductRating.objects.filter(
            product_id=product_id, user_id=user_id
        ).first()

        if existing_rating:
            return True, "You can update your existing rating"

        return True, "You can rate this product"

    @staticmethod
    @transaction.atomic
    def add_or_update_rating(
        product_id: int,
        user_id: int,
        rating: int,
        review: str,
        title: str = "",
        is_verified_purchase: bool = True,
    ) -> ProductRating:
        """
        Add a new rating or update an existing rating (same user + same product).
        Once saved, enqueue an asynchronous aggregate‐recalculation task and clear caches.
        """
        # Get purchase date for verification
        from apps.transactions.models import EscrowTransaction

        purchase_transaction = (
            EscrowTransaction.objects.filter(
                product_id=product_id, buyer_id=user_id, status="completed"
            )
            .order_by("-created_at")
            .first()
        )

        purchase_date = (
            purchase_transaction.created_at if purchase_transaction else None
        )

        # Create or update the ProductRating row
        rating_obj, created = ProductRating.objects.update_or_create(
            product_id=product_id,
            user_id=user_id,
            defaults={
                "rating": rating,
                "review": review,
                "title": title,
                "is_verified_purchase": is_verified_purchase,
                "purchase_date": purchase_date,
                "is_approved": True,  # Auto-approve verified purchases
            },
        )

        # Trigger aggregate update
        ProductRatingService.trigger_rating_aggregate_update(product_id=product_id)

        # Clear caches
        ProductRatingService._clear_product_caches(product_id)

        return rating_obj

    @staticmethod
    @transaction.atomic
    def update_existing_rating(
        rating_id: int,
        rating: int,
        review: str,
        title: str = "",
    ) -> ProductRating:
        """Update an existing rating"""
        rating_obj = ProductRating.objects.get(id=rating_id)
        rating_obj.rating = rating
        rating_obj.review = review
        rating_obj.title = title
        rating_obj.updated_at = timezone.now()
        rating_obj.save()

        # Trigger aggregate update
        ProductRatingService.trigger_rating_aggregate_update(
            product_id=rating_obj.product_id
        )

        # Clear caches
        ProductRatingService._clear_product_caches(rating_obj.product_id)

        return rating_obj

    @staticmethod
    def _clear_product_caches(product_id: int):
        """Clear all caches related to a product's ratings"""
        redis_conn = get_redis_connection("default")
        # django-redis strips KEY_PREFIX for you
        # cache.delete("safetrade:product_base:list:main")
        logger.info("Deleting list caches with pattern")
        raw_keys = redis_conn.smembers(ProductRatingService.LIST_KEYS_SET)
        decoded_keys = [k.decode("utf-8") for k in raw_keys]
        print(decoded_keys)
        for key in decoded_keys:
            logger.info(f"Deleted single key: {key}")
            cache.delete(key)
            logger.info(f"✅ Deleted {key} list cache keys")

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
    def get_cache_key(**kwargs) -> str:
        """Generate a cache key based on the view name and parameters."""
        product_id = kwargs.get("product_id")
        params_str = json.dumps(kwargs, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

        key = CacheKeyManager.make_key(
            "product_rating", "list", product_id=product_id, params=params_hash
        )
        redis_conn = get_redis_connection("default")
        redis_conn.sadd(ProductRatingService.LIST_KEYS_SET, key)
        logger.info(f"Generated cache key: {key} with params: {params_hash}")

        return key

    @staticmethod
    def get_product_ratings(
        product_id: int,
        page: int = 1,
        per_page: int = 10,
        filter_rating: int = None,
        sort_by: str = "newest",
        show_verified_only: bool = False,
    ) -> Dict:
        """
        Return a paginated list of approved ratings for a product, with optional filter/sort.
        Caches the result for CACHE_TIMEOUT seconds.
        """
        cache_key = ProductRatingService.get_cache_key(
            page=page,
            product_id=product_id,
            per_page=per_page,
            filter_rating=filter_rating or "all",
            sort_by=sort_by,
            verified_only=show_verified_only,
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        queryset = ProductRating.objects.filter(
            product_id=product_id, is_approved=True
        ).select_related("user")

        if filter_rating:
            queryset = queryset.filter(rating=filter_rating)

        if show_verified_only:
            queryset = queryset.filter(is_verified_purchase=True)

        # Sorting options
        if sort_by == "helpful":
            queryset = queryset.order_by("-helpful_count", "-created_at")
        elif sort_by == "rating_high":
            queryset = queryset.order_by("-rating", "-created_at")
        elif sort_by == "rating_low":
            queryset = queryset.order_by("rating", "-created_at")
        elif sort_by == "oldest":
            queryset = queryset.order_by("created_at")
        else:  # "newest" by default
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
    def get_user_ratings(
        user_id: int,
        page: int = 1,
        per_page: int = 10,
    ) -> Dict:
        """Get paginated ratings by a specific user"""
        cache_key = CacheKeyManager.make_key(
            "product_rating",
            "user_list",
            user_id=user_id,
            params={"page": page, "per_page": per_page},
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        queryset = (
            ProductRating.objects.filter(user_id=user_id, is_approved=True)
            .select_related("product")
            .order_by("-created_at")
        )

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
        Create or update a "helpful" vote on a rating, and update that rating's helpful_count/total_votes.
        Returns True if a new vote was created, False if an existing vote was updated.
        """
        # Prevent users from voting on their own ratings
        rating = ProductRating.objects.get(id=rating_id)
        if rating.user_id == user_id:
            raise ValueError("You cannot vote on your own rating")

        vote, created = RatingHelpfulness.objects.update_or_create(
            rating_id=rating_id, user_id=user_id, defaults={"is_helpful": is_helpful}
        )

        # Recalculate vote counts
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
        cache_key = CacheKeyManager.make_key(
            "product_rating", "aggregate", product_id=product_id
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
            try:
                aggregate = ProductRatingAggregate.objects.get(product_id=product_id)
                cache.set(cache_key, aggregate, ProductRatingService.CACHE_TIMEOUT)
                return aggregate
            except ProductRatingAggregate.DoesNotExist:
                return None

    @staticmethod
    def get_user_rating_stats(user_id: int) -> Dict:
        """Get statistics about a user's rating activity"""
        cache_key = CacheKeyManager.make_key(
            "product_rating", "user_stats", user_id=user_id
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        user_ratings = ProductRating.objects.filter(user_id=user_id, is_approved=True)

        stats = user_ratings.aggregate(
            total_ratings=Count("id"),
            average_rating_given=Avg("rating"),
            verified_purchases_rated=Count("id", filter=Q(is_verified_purchase=True)),
            helpful_votes_received=Count(
                "helpfulness_votes", filter=Q(helpfulness_votes__is_helpful=True)
            ),
        )

        result = {
            "total_ratings": stats["total_ratings"] or 0,
            "average_rating_given": round(stats["average_rating_given"] or 0, 2),
            "verified_purchases_rated": stats["verified_purchases_rated"] or 0,
            "helpful_votes_received": stats["helpful_votes_received"] or 0,
        }

        cache.set(cache_key, result, ProductRatingService.CACHE_TIMEOUT)
        return result

    @staticmethod
    def get_recent_ratings(limit: int = 10) -> list:
        """Get recent ratings across all products for admin/analytics"""
        return (
            ProductRating.objects.filter(is_approved=True)
            .select_related("user", "product")
            .order_by("-created_at")[:limit]
        )

    @staticmethod
    def flag_rating(rating_id: int, reason: str, flagged_by_user_id: int) -> bool:
        """Flag a rating for moderation"""
        try:
            rating = ProductRating.objects.get(id=rating_id)
            if rating.user_id == flagged_by_user_id:
                raise ValueError("You cannot flag your own rating")

            rating.is_flagged = True
            rating.flagged_reason = reason
            rating.save(update_fields=["is_flagged", "flagged_reason"])

            # Could trigger a notification to moderators here
            return True
        except ProductRating.DoesNotExist:
            return False

    @staticmethod
    def moderate_rating(rating_id: int, approve: bool, moderator_user_id: int) -> bool:
        """Approve or reject a flagged rating"""
        try:
            rating = ProductRating.objects.get(id=rating_id)
            rating.is_approved = approve
            rating.is_flagged = False if approve else rating.is_flagged
            rating.save(update_fields=["is_approved", "is_flagged"])

            # If status changed, update aggregates
            if rating.is_approved != approve:
                ProductRatingService.trigger_rating_aggregate_update(rating.product_id)
                ProductRatingService._clear_product_caches(rating.product_id)

            return True
        except ProductRating.DoesNotExist:
            return False

    # ────────────────────────────────────────────────────
    # CELERY TASK-ENQUEUE "TRIGGERS" (lazy imports to avoid circular import)
    # ────────────────────────────────────────────────────

    @staticmethod
    def trigger_rating_aggregate_update(product_id: int, delay_seconds: int = 0):
        """
        Enqueue (or schedule) the debounced Celery task to recalc aggregates for one product.
        If delay_seconds > 0, schedule it in the future; otherwise queue immediately.
        """
        from .tasks import debounced_rating_aggregate_update

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
        from .tasks import bulk_update_rating_aggregates_task

        return bulk_update_rating_aggregates_task.delay(product_ids)

    @staticmethod
    def schedule_rating_aggregate_update(product_id: int, eta_datetime=None):
        """
        Schedule a debounced update at an exact datetime (`eta_datetime` must be a timezone‐aware datetime).
        """
        from .tasks import debounced_rating_aggregate_update

        return debounced_rating_aggregate_update.apply_async(
            args=[product_id], eta=eta_datetime
        )

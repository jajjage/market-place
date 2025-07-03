import logging
from decimal import Decimal
from django.db import IntegrityError
from django.db.models import Avg, Count
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from rest_framework import serializers
from .models import UserRating
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.transactions.models import EscrowTransaction

logger = logging.getLogger(__name__)


class RatingService:

    @staticmethod
    def get_user_rating_stats(user_id, use_cache=True):
        """Get aggregated rating statistics for a user (seller)"""
        cache_key = CacheKeyManager.make_key("rating", "stats", user_id=user_id)

        if use_cache:
            cached_stats = cache.get(cache_key)
            if cached_stats:
                logger.info(f"Rating stats cache hit for user {user_id}")
                return cached_stats

        start_time = timezone.now()

        # Get ratings with optimized query
        ratings_qs = UserRating.objects.filter(to_user_id=user_id).select_related(
            "from_user", "transaction"
        )

        # Calculate aggregations
        stats = ratings_qs.aggregate(
            average_rating=Avg("rating"), total_ratings=Count("id")
        )

        # Rating distribution
        distribution = {}
        for i in range(1, 6):
            count = ratings_qs.filter(rating=i).count()
            distribution[f"{i}_star"] = count

        # Recent ratings (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_count = ratings_qs.filter(created_at__gte=thirty_days_ago).count()

        result = {
            "average_rating": stats["average_rating"] or Decimal("0.00"),
            "total_ratings": stats["total_ratings"],
            "rating_distribution": distribution,
            "recent_ratings_count": recent_count,
        }

        # Cache for 1 hour
        if use_cache:
            cache.set(cache_key, result, 3600)

        elapsed = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Calculated rating stats for user {user_id} in {elapsed:.2f}ms")

        return result

    @staticmethod
    def check_rating_eligibility(transaction_id, user):
        """Check if user can rate the transaction"""
        try:
            transaction = EscrowTransaction.objects.select_related(
                "buyer", "seller"
            ).get(id=transaction_id)
        except EscrowTransaction.DoesNotExist:
            return {
                "can_rate": False,
                "reason": "Transaction not found",
                "expires_at": None,
                "transaction_id": transaction_id,
                "seller_name": None,
            }

        # Check if user is buyer
        if user != transaction.buyer:
            return {
                "can_rate": False,
                "reason": "Only buyers can rate sellers",
                "expires_at": None,
                "transaction_id": transaction_id,
                "seller_name": transaction.seller.get_full_name(),
            }

        # Check transaction status
        if transaction.status not in ["completed", "funds_released"]:
            return {
                "can_rate": False,
                "reason": "Transaction must be completed to rate",
                "expires_at": None,
                "transaction_id": transaction_id,
                "seller_name": transaction.seller.get_full_name(),
            }

        # Check if already rated THIS specific transaction
        existing_rating = UserRating.objects.filter(
            from_user=user, transaction=transaction
        ).first()

        if existing_rating:
            return {
                "can_rate": False,
                "reason": "You have already rated this transaction",
                "expires_at": None,
                "transaction_id": transaction_id,
                "seller_name": transaction.seller.get_full_name(),
                "existing_rating_id": existing_rating.id,
            }

        # Check completion date
        if not transaction.status_changed_at:
            return {
                "can_rate": False,
                "reason": "Transaction completion date is missing",
                "expires_at": None,
                "transaction_id": transaction_id,
                "seller_name": transaction.seller.get_full_name(),
            }

        # Check rating window
        now = timezone.now()
        rating_deadline = transaction.status_changed_at + timedelta(days=30)

        if now > rating_deadline:
            return {
                "can_rate": False,
                "reason": "Rating period has expired",
                "expires_at": rating_deadline,
                "transaction_id": transaction_id,
                "seller_name": transaction.seller.get_full_name(),
            }

        return {
            "can_rate": True,
            "reason": "You can rate this transaction",
            "expires_at": rating_deadline,
            "transaction_id": transaction_id,
            "seller_name": transaction.seller.get_full_name(),
        }

    @staticmethod
    def check_buyer_seller_rating_eligibility(buyer_id, seller_id):
        """
        Check if buyer can rate seller based on their transaction history
        This is the robust approach for profile-based rating eligibility
        """
        cache_key = CacheKeyManager.make_key(
            "rating", "eligibility", buyer_id=buyer_id, seller_id=seller_id
        )
        cached_result = cache.get(cache_key)

        if cached_result:
            logger.info(
                f"Rating eligibility cache hit for buyer {buyer_id}, seller {seller_id}"
            )
            return cached_result

        start_time = timezone.now()

        # Get seller info for response
        try:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            seller = User.objects.get(id=seller_id)
            seller_name = seller.get_full_name()
        except User.DoesNotExist:
            return {
                "can_rate": False,
                "reason": "Seller not found",
                "rateable_transactions": [],
                "total_completed_transactions": 0,
                "seller_name": None,
                "seller_id": seller_id,
            }

        # Check if buyer and seller are the same person
        if buyer_id == seller_id:
            result = {
                "can_rate": False,
                "reason": "You cannot rate yourself",
                "rateable_transactions": [],
                "total_completed_transactions": 0,
                "seller_name": seller_name,
                "seller_id": seller_id,
            }
            cache.set(cache_key, result, 1800)  # Cache for 30 minutes
            return result

        # Get all completed transactions between buyer and seller
        thirty_days_ago = timezone.now() - timedelta(days=30)

        completed_transactions = (
            EscrowTransaction.objects.filter(
                buyer_id=buyer_id,
                seller_id=seller_id,
                status__in=[
                    "completed",
                    "funds_released",
                ],  # Both completed and funds_released
                status_changed_at__isnull=False,
            )
            .select_related("seller")
            .order_by("-status_changed_at")
        )

        total_completed = completed_transactions.count()

        if total_completed == 0:
            result = {
                "can_rate": False,
                "reason": "No completed transactions with this seller",
                "rateable_transactions": [],
                "total_completed_transactions": 0,
                "seller_name": seller_name,
                "seller_id": seller_id,
            }
            cache.set(cache_key, result, 1800)
            return result

        # Find transactions that can be rated
        rateable_transactions = []

        for transaction in completed_transactions:
            # Check if rating window is still valid (30 days)
            rating_deadline = transaction.status_changed_at + timedelta(days=30)
            now = timezone.now()

            if now > rating_deadline:
                continue  # Skip expired transactions

            # Check if already rated THIS specific transaction
            existing_rating = UserRating.objects.filter(
                from_user_id=buyer_id, transaction=transaction
            ).first()
            if existing_rating:
                continue

            days_remaining = (rating_deadline - now).days

            rateable_transactions.append(
                {
                    "transaction_id": transaction.id,
                    "transaction_title": transaction.notes,
                    "transaction_amount": str(transaction.total_amount),
                    "status_changed_at": transaction.status_changed_at,
                    "rating_deadline": rating_deadline,
                    "days_remaining": max(0, days_remaining),
                }
            )

        # Determine overall eligibility
        can_rate = len(rateable_transactions) > 0

        if can_rate:
            reason = f"You can rate {len(rateable_transactions)} transaction(s) with this seller"
        else:
            # Check why they can't rate
            already_rated_count = completed_transactions.filter(
                rating__isnull=False
            ).count()
            expired_count = (
                total_completed - already_rated_count - len(rateable_transactions)
            )

            if already_rated_count == total_completed:
                reason = "You have already rated all transactions with this seller"
            elif expired_count > 0:
                reason = (
                    "Rating period has expired for all transactions with this seller"
                )
            else:
                reason = "No rateable transactions found with this seller"

        result = {
            "can_rate": can_rate,
            "reason": reason,
            "rateable_transactions": rateable_transactions,
            "total_completed_transactions": total_completed,
            "seller_name": seller_name,
            "seller_id": seller_id,
        }

        # Cache for 30 minutes
        cache.set(cache_key, result, 1800)

        elapsed = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(
            f"Checked rating eligibility for buyer {buyer_id}, seller {seller_id} in {elapsed:.2f}ms"
        )

        return result

    @staticmethod
    def get_pending_ratings_for_user(user, limit=None):
        """Get transactions where user can still provide ratings"""
        cache_key = CacheKeyManager.make_key("rating", "pending", user_id=user.id)
        cached_result = cache.get(cache_key)

        if cached_result:
            logger.info(f"Pending ratings cache hit for user {user.id}")
            return cached_result

        start_time = timezone.now()

        # Get completed transactions without ratings
        thirty_days_ago = timezone.now() - timedelta(days=30)

        transactions = (
            EscrowTransaction.objects.filter(
                buyer=user,
                status__in=["completed", "funds_released"],
                status_changed_at__gte=thirty_days_ago,
            )
            .exclude(rating__isnull=False)
            .select_related("seller")
            .order_by("-status_changed_at")
        )

        if limit:
            transactions = transactions[:limit]

        pending_ratings = []
        for transaction in transactions:
            expires_at = transaction.status_changed_at + timedelta(days=30)
            days_remaining = (expires_at - timezone.now()).days

            pending_ratings.append(
                {
                    "transaction_id": transaction.id,
                    "transaction_title": transaction.notes,
                    "seller_name": transaction.seller.get_full_name(),
                    "status_changed_at": transaction.status_changed_at,
                    "expires_at": expires_at,
                    "days_remaining": max(0, days_remaining),
                }
            )

        # Cache for 15 minutes
        cache.set(cache_key, pending_ratings, 900)

        elapsed = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(
            f"Retrieved {len(pending_ratings)} pending ratings for user {user.id} in {elapsed:.2f}ms"
        )

        return pending_ratings

    @staticmethod
    def create_rating(transaction_id, user, rating_data):
        """Create a rating with full business logic validation"""

        logger.info(
            f"Creating rating for transaction {transaction_id} by user {user.id}"
        )
        # Get transaction first
        try:
            transaction = EscrowTransaction.objects.select_related(
                "seller", "buyer"
            ).get(id=transaction_id)
        except EscrowTransaction.DoesNotExist:
            raise serializers.ValidationError("Transaction not found")
        logger.info(
            f"Transaction found: {transaction} for user {user.id}, status: {transaction.status}"
        )

        # Validate user is the buyer
        if user != transaction.buyer:
            raise serializers.ValidationError("Only buyers can rate sellers")

        # Check transaction status
        ALLOWED = {"completed", "funds_released"}
        status = transaction.status
        if status not in ALLOWED:
            logger.info(f"Transaction status: {status}")
            raise serializers.ValidationError(
                {"non_field_errors": "Transaction must be completed to rate from here"}
            )

        if not transaction.status_changed_at:
            raise serializers.ValidationError("Transaction completion date is required")

        # Check if already rated THIS specific transaction
        existing_rating = UserRating.objects.filter(
            from_user=user, transaction=transaction
        ).first()

        if existing_rating:
            raise serializers.ValidationError("You have already rated this transaction")

        # Check rating window (30 days)
        now = timezone.now()
        rating_deadline = transaction.status_changed_at + timedelta(days=30)
        if now > rating_deadline:
            raise serializers.ValidationError(
                "Rating period has expired (30 days after completion)"
            )

        # Create rating
        try:
            rating = UserRating.objects.create(
                transaction=transaction,
                from_user=user,
                to_user=transaction.seller,
                is_verified=True,
                **rating_data,
            )
        except IntegrityError as e:
            if "unique" in str(e).lower():
                raise serializers.ValidationError(
                    "You have already rated this transaction"
                )
            raise serializers.ValidationError("Failed to create rating")

        # Invalidate caches
        RatingService.invalidate_user_rating_cache(rating.to_user.id)
        RatingService.invalidate_user_rating_cache(rating.from_user.id)

        # Trigger async tasks
        try:
            from .tasks import update_rating_stats, send_rating_notifications

            update_rating_stats.delay(rating.to_user.id)
            send_rating_notifications.delay(rating.id)
        except ImportError:
            logger.warning("Rating tasks not available")

        logger.info(
            f"Rating created: {rating.id} by user {user.id} for transaction {transaction_id}"
        )
        return rating

    @staticmethod
    def get_user_ratings_list(user_id, page=None, use_cache=True):
        """Get paginated list of ratings for a user with caching"""
        if use_cache and page:
            cache_key = CacheKeyManager.make_key(
                "rating", "list", user_id=user_id, page=page
            )
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Rating list cache hit for user {user_id}, page {page}")
                return cached_response, True

        start_time = timezone.now()

        queryset = (
            UserRating.objects.filter(to_user_id=user_id)
            .select_related("from_user", "transaction")
            .order_by("-created_at")
        )

        elapsed = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Retrieved ratings for user {user_id} in {elapsed:.2f}ms")

        return queryset, False

    @staticmethod
    def get_user_given_ratings(user):
        """Get ratings given by a user"""
        return (
            UserRating.objects.filter(from_user=user)
            .select_related("to_user", "transaction")
            .order_by("-created_at")
        )

    @staticmethod
    def get_user_received_ratings(user):
        """Get ratings received by a user"""
        return (
            UserRating.objects.filter(to_user=user)
            .select_related("from_user", "transaction")
            .order_by("-created_at")
        )

    @staticmethod
    def invalidate_user_rating_cache(user_id):
        """Invalidate all rating-related cache for a user"""
        CacheManager.invalidate("rating", user_id=user_id)
        logger.info(f"Invalidated rating cache for user {user_id}")

    @staticmethod
    def get_transaction_id_from_request(request):
        """Extract transaction_id from request data, query params, or URL"""
        # Check request data first
        transaction_id = request.data.get("transaction_id")

        if not transaction_id:
            # Check query parameters
            transaction_id = request.query_params.get("transaction_id")

        if not transaction_id:
            # Check URL kwargs (if transaction_id is in URL)
            transaction_id = (
                getattr(request, "parser_context", {})
                .get("kwargs", {})
                .get("transaction_id")
            )

        return transaction_id

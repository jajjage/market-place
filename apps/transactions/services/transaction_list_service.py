from django.core.cache import cache
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404
from django_redis import get_redis_connection
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.transactions.models import EscrowTransaction, TransactionHistory
from apps.transactions.serializers import (
    EscrowTransactionListSerializer,
    EscrowTransactionTrackingSerializer,
    ProductTrackingSerializer,
    TransactionHistorySerializer,
)
import logging
import time
import json
import hashlib

logger = logging.getLogger("transactions_performance")


class TransactionListService:
    """Service for handling transaction list operations with caching and optimization"""

    CACHE_TTL = 60 * 5  # 5 minutes cache
    TRACKING_CACHE_TTL = 60 * 2  # 2 minutes

    @classmethod
    def get_transaction_list(
        cls,
        user,
        queryset,
        status_filter=None,
        search_query=None,
        ordering=None,
        offset: int = 0,
        limit: int = 20,
        cache_key_suffix="list",
    ):
        """
        Get optimized transaction list with caching

        Args:
            user: The requesting user
            queryset: Base queryset from the view
            status_filter: Optional status filter
            search_query: Optional search query
            ordering: Optional ordering
            cache_key_suffix: Suffix for cache key (list, purchases, sales)

        Returns:
            dict: Contains 'data' and 'from_cache' boolean
        """
        start_time = time.time()

        # Create parameters for hashing (include user_id for uniqueness)
        params = {
            "type": cache_key_suffix,
            "status": status_filter or "all",
            "search": search_query or "none",
            "ordering": ordering[0] if ordering else "default",
            "offset": offset,
            "limit": limit,
        }

        # Create hash from parameters
        params_str = json.dumps(params, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

        # Create cache key with user_id and params_hash
        cache_key = CacheKeyManager.make_key(
            "escrow_transaction", "list_user", user_id=user.id, params=params_hash
        )
        logger.info(f"cache key:{cache_key} ")
        # Store cache key for later invalidation
        cls._store_cache_key(cache_key)

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            elapsed = (time.time() - start_time) * 1000
            logger.info(
                f"Cache hit for user {user.id} transactions ({cache_key_suffix}) in {elapsed:.2f}ms"
            )
            return {"data": cached_data, "from_cache": True}

        # Build optimized queryset
        optimized_queryset = cls._build_optimized_queryset(queryset)

        # Apply filters
        if status_filter:
            optimized_queryset = optimized_queryset.filter(status=status_filter)

        if search_query:
            optimized_queryset = cls._apply_search_filter(
                optimized_queryset, search_query
            )

        # Apply ordering
        if ordering:
            optimized_queryset = optimized_queryset.order_by(*ordering)

        # Execute query and serialize
        transactions = list(optimized_queryset)
        serializer = EscrowTransactionListSerializer(transactions, many=True)
        serialized_data = serializer.data

        # Cache the result
        cache.set(cache_key, serialized_data, cls.CACHE_TTL)

        elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"Fetched {len(serialized_data)} transactions ({cache_key_suffix}) for user {user.id} in {elapsed:.2f}ms"
        )

        return {"data": serialized_data, "from_cache": False}

    @classmethod
    def get_user_purchases(
        cls,
        user,
        queryset,
        status_filter=None,
        search_query=None,
        ordering=None,
        offset=0,
        limit=20,
    ):
        """Get user's purchase transactions"""
        purchase_queryset = queryset.filter(buyer=user)
        return cls.get_transaction_list(
            user=user,
            queryset=purchase_queryset,
            status_filter=status_filter,
            search_query=search_query,
            ordering=ordering,
            offset=int(offset),
            limit=int(limit),
            cache_key_suffix="purchases",
        )

    @classmethod
    def get_user_sales(
        cls,
        user,
        queryset,
        status_filter=None,
        search_query=None,
        ordering=None,
        offset=0,
        limit=20,
    ):
        """Get user's sales transactions"""
        sales_queryset = queryset.filter(seller=user)
        return cls.get_transaction_list(
            user=user,
            queryset=sales_queryset,
            status_filter=status_filter,
            search_query=search_query,
            ordering=ordering,
            offset=int(offset),
            limit=int(limit),
            cache_key_suffix="sales",
        )

    @classmethod
    def get_user_all_transactions(
        cls,
        user,
        queryset,
        status_filter=None,
        search_query=None,
        ordering=None,
        offset=0,
        limit=20,
    ):
        """Get all transactions where user is involved (buyer or seller)"""
        user_queryset = queryset.filter(Q(buyer=user) | Q(seller=user))
        return cls.get_transaction_list(
            user=user,
            queryset=user_queryset,
            status_filter=status_filter,
            search_query=search_query,
            ordering=ordering,
            offset=int(offset),
            limit=int(limit),
            cache_key_suffix="all",
        )

    @classmethod
    def _build_optimized_queryset(cls, queryset):
        return queryset.select_related(
            "buyer", "seller", "product", "product__category", "product__brand"
        ).prefetch_related(
            # fetch *all* history, but attach it to a custom attr
            Prefetch(
                "history",
                queryset=TransactionHistory.objects.select_related(
                    "created_by"
                ).order_by("-timestamp"),
                to_attr="all_history",  # <— store in instance.all_history
            ),
            "product__images",
            "product__variants",
        )

    @classmethod
    def _apply_search_filter(cls, queryset, search_query):
        """Apply search filter to queryset"""
        return queryset.filter(
            Q(tracking_id__icontains=search_query)
            | Q(product__title__icontains=search_query)
            | Q(buyer__email__icontains=search_query)
            | Q(seller__email__icontains=search_query)
            | Q(buyer__first_name__icontains=search_query)
            | Q(buyer__last_name__icontains=search_query)
            | Q(seller__first_name__icontains=search_query)
            | Q(seller__last_name__icontains=search_query)
        )

    @classmethod
    def get_tracking(cls, tracking_id, user):
        start = time.time()

        # build a cache key unique per tracking_id + user (you may omit user if tracking_ids are secret)
        cache_key = CacheKeyManager.make_key(
            "escrow_transaction", "tracking", user_id=user.id, tracking_id=tracking_id
        )

        # try cache
        payload = cache.get(cache_key)
        if payload:
            logger.info(
                f"Track cache HIT for {tracking_id} in {(time.time() - start) * 1000:.1f}ms"
            )
            return payload, True

        # miss → load from DB
        tx = get_object_or_404(EscrowTransaction, tracking_id=tracking_id)

        # permission check
        if not user.is_staff and user not in (tx.buyer, tx.seller):
            from rest_framework import exceptions

            raise exceptions.PermissionDenied(
                "You do not have permission to view this transaction"
            )

        # fetch history & serialize
        hist_qs = TransactionHistory.objects.filter(transaction=tx).order_by(
            "timestamp"
        )
        tx_data = EscrowTransactionTrackingSerializer(tx).data
        hist_data = TransactionHistorySerializer(hist_qs, many=True).data

        tx_data["history"] = hist_data
        tx_data["product_details"] = ProductTrackingSerializer(tx.product).data

        if tx.status in ["shipped", "delivered"]:
            tx_data["shipping_info"] = {
                "tracking_number": tx.tracking_number,
                "shipping_carrier": tx.shipping_carrier,
                "status_updates": hist_data,
            }

        # cache and return
        cache.set(cache_key, tx_data, cls.TRACKING_CACHE_TTL)
        logger.info(
            f"Track cache MISS for {tracking_id} in {(time.time() - start) * 1000:.1f}ms"
        )
        return tx_data, False

    @classmethod
    def _store_cache_key(cls, cache_key):
        """Store cache key in Redis set for batch invalidation"""
        redis_conn = get_redis_connection("default")
        # Store the cache key in a set for later batch deletion
        redis_conn.sadd("safetrade:escrow_transaction:list_user:keys", cache_key)
        logger.debug(f"Stored cache key: {cache_key}")

    @classmethod
    def invalidate_user_transaction_caches(cls, user_id):
        """Invalidate all transaction caches for a specific user"""
        redis_conn = get_redis_connection("default")

        # Get all stored cache keys
        keys = redis_conn.smembers("safetrade:escrow_transaction:list_user:keys")
        decoded_keys = [k.decode("utf-8") for k in keys]

        # Filter keys that belong to this user
        user_keys = [key for key in decoded_keys if f"{user_id}" in key]

        if user_keys:
            logger.info(f"Deleting {len(user_keys)} cache keys for user {user_id}")
            for key in user_keys:
                cache.delete(key)
                # Remove from the set
                redis_conn.srem("safetrade:escrow_transaction:list_user:keys", key)
                logger.info(f"✅ Deleted cache key: {key}")
        else:
            logger.warning(f"⚠️ No transaction cache keys found for user {user_id}")

    @classmethod
    def invalidate_all_transaction_list_caches(cls):
        """Invalidate all transaction list caches"""
        redis_conn = get_redis_connection("default")

        logger.info("Deleting all transaction list caches")
        keys = redis_conn.smembers("safetrade:escrow_transaction:list_user:keys")
        decoded_keys = [k.decode("utf-8") for k in keys]

        if decoded_keys:
            for key in decoded_keys:
                cache.delete(key)
                logger.info(f"Deleted cache key: {key}")

            # Clear the keys set
            redis_conn.delete("safetrade:escrow_transaction:list_user:keys")
            logger.info(f"✅ Deleted {len(decoded_keys)} transaction list cache keys")
        else:
            logger.warning("⚠️ No transaction list cache keys found to delete")

    @classmethod
    def invalidate_transaction_caches(cls, transaction):
        """Invalidate specific transaction caches for both buyer and seller"""
        # Invalidate caches for both buyer and seller since they're both affected
        cls.invalidate_user_transaction_caches(transaction.buyer.id)
        cls.invalidate_user_transaction_caches(transaction.seller.id)

        logger.info(
            f"Invalidated caches for transaction {transaction.id} (buyer: {transaction.buyer.id}, seller: {transaction.seller.id})"
        )

    @classmethod
    def invalidate_tracking_cache(cls, transaction=None, tracking_id=None):
        """Invalidate either one or all tracking caches."""
        CacheManager.invalidate_key(
            "escrow_transaction",
            "tracking",
            user_id=transaction.buyer.id,
            tracking_id=tracking_id,
        )
        CacheManager.invalidate_key(
            "escrow_transaction",
            "tracking",
            user_id=transaction.seller.id,
            tracking_id=tracking_id,
        )
        # redis_conn = get_redis_connection("default")
        # keys = redis_conn.smembers("safetrade:escrow_tracking:keys")
        # for raw in keys:
        #     key = raw.decode("utf-8")
        #     if tracking_id is None or tracking_id in key:
        #         cache.delete(key)
        #         redis_conn.srem("safetrade:escrow_tracking:keys", key)
        #         logger.info(f"Invalidated tracking cache key: {key}")

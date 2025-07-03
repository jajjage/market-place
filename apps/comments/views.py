import uuid
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
import logging

from apps.core.views import BaseViewSet

from .models import UserRating
from .serializers import (
    RatingCreateSerializer,
    RatingDetailSerializer,
    RatingListSerializer,
    RatingEligibilitySerializer,
    BuyerSellerEligibilitySerializer,
    RatingStatsSerializer,
    PendingRatingSerializer,
)
from .services import RatingService
from .permissions import CanRateTransactionPermission
from .throttling import RatingCreateThrottle, RatingViewThrottle
from apps.core.utils.cache_manager import CacheKeyManager

logger = logging.getLogger(__name__)


class RatingViewSet(BaseViewSet):
    """
    ViewSet for managing ratings with all endpoints:
    - POST /ratings/ - Create rating (requires transaction_id in data/query)
    - GET /ratings/ - List all ratings for authenticated user (received)
    - GET /ratings/{id}/ - Get specific rating detail
    - GET /ratings/eligibility/ - Check rating eligibility (requires transaction_id)
    - GET /ratings/stats/ - Get user rating stats (requires user_id)
    - GET /ratings/pending/ - Get pending ratings for authenticated user
    - GET /ratings/given/ - Get ratings given by authenticated user
    - GET /ratings/received/ - Get ratings received by authenticated user
    - GET /ratings/user/{user_id}/ - Get ratings for specific user
    """

    queryset = UserRating.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [RatingViewThrottle]

    def get_serializer_class(self):
        if self.action == "create":
            return RatingCreateSerializer
        elif self.action in ["eligibility"]:
            return RatingEligibilitySerializer
        elif self.action == "stats":
            return RatingStatsSerializer
        elif self.action == "pending":
            return PendingRatingSerializer
        elif self.action in ["list", "user_ratings"]:
            return RatingListSerializer
        else:
            return RatingDetailSerializer

    def get_throttles(self):
        if self.action == "create":
            return [RatingCreateThrottle()]
        return super().get_throttles()

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), CanRateTransactionPermission()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """Create a rating for a completed transaction"""
        # Get transaction_id from multiple sources
        transaction_id = RatingService.get_transaction_id_from_request(request)
        logger.info(
            f"Creating rating for transaction_id: {transaction_id}, user: {request.user.id}"
        )

        if not transaction_id:
            return self.error_response(
                message="transaction_id is required in data or query parameters",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            transaction_id = uuid.UUID(transaction_id)
        except (ValueError, TypeError):
            return self.error_response(
                message="transaction_id must be a valid UUID",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rating = RatingService.create_rating(
                transaction_id=transaction_id,
                user=request.user,
                rating_data=serializer.validated_data,
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

        response_serializer = RatingDetailSerializer(rating)
        return self.success_response(
            data=response_serializer.data, status_code=status.HTTP_201_CREATED
        )

    def list(self, request, *args, **kwargs):
        """List ratings received by authenticated user"""
        queryset = RatingService.get_user_received_ratings(request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["get"])
    def eligibility(self, request):
        """
        Check if user can rate a seller based on their transaction history
        Supports both approaches:
        1. New: ?seller_id=123 (robust profile-based approach)
        2. Legacy: ?transaction_id=123 (backward compatibility)
        """
        seller_id = request.query_params.get("seller_id")
        transaction_id = request.query_params.get("transaction_id")

        if seller_id:
            # New robust approach: Check buyer-seller relationship
            try:
                seller_id = uuid.UUID(seller_id)
            except (ValueError, TypeError):
                return self.error_response(
                    message="seller_id must be a valid UUID",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            eligibility_result = RatingService.check_buyer_seller_rating_eligibility(
                buyer_id=request.user.id, seller_id=seller_id
            )
            serializer = BuyerSellerEligibilitySerializer(eligibility_result)
            return self.success_response(data=serializer.data)

        elif transaction_id:
            # Legacy approach: Check specific transaction
            try:
                transaction_id = uuid.UUID(transaction_id)
            except (ValueError, TypeError):
                return self.error_response(
                    message="transaction_id must be a valid UUID",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            eligibility_result = RatingService.check_rating_eligibility(
                transaction_id, request.user
            )
            serializer = self.get_serializer(eligibility_result)
            return self.success_response(data=serializer.data)

        else:
            return self.error_response(
                message="Either seller_id or transaction_id query parameter is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get aggregated rating statistics for a user"""
        user_id = request.query_params.get("user_id")

        if not user_id:
            # Default to authenticated user
            user_id = request.user.id

        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "user_id must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stats = RatingService.get_user_rating_stats(user_id)
        serializer = self.get_serializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """List transactions where authenticated user can still provide ratings"""
        limit = request.query_params.get("limit")
        if limit:
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                return Response(
                    {"error": "limit must be a valid integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        pending_ratings = RatingService.get_pending_ratings_for_user(
            request.user, limit
        )
        serializer = self.get_serializer(pending_ratings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def given(self, request):
        """List ratings given by authenticated user"""
        queryset = RatingService.get_user_given_ratings(request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = RatingDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = RatingDetailSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def received(self, request):
        """List ratings received by authenticated user"""
        queryset = RatingService.get_user_received_ratings(request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = RatingDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = RatingDetailSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="user/(?P<user_id>[^/.]+)")
    def user_ratings(self, request, user_id=None):
        """List ratings received by a specific user"""
        if not user_id:
            return self.error_response(
                message="user_id is required", status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_id = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return self.error_response(
                message="user_id must be a valid UUID",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        start_time = timezone.now()

        # Check cache first
        page_num = request.query_params.get("page", 1)
        cache_key = CacheKeyManager.make_key(
            "rating", "list", user_id=user_id, page=page_num
        )
        cached_response = cache.get(cache_key)

        if cached_response:
            logger.info(f"Rating list cache hit for user {user_id}, page {page_num}")
            return self.success_response(data=cached_response)

        queryset, _ = RatingService.get_user_ratings_list(
            user_id, page_num, use_cache=False
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data

            # Cache for 10 minutes
            cache.set(cache_key, response_data, 600)

            elapsed = (timezone.now() - start_time).total_seconds() * 1000
            logger.info(f"Retrieved ratings for user {user_id} in {elapsed:.2f}ms")

            return Response(response_data)

        serializer = self.get_serializer(queryset, many=True)
        response_data = serializer.data

        # Cache for 10 minutes
        cache.set(cache_key, response_data, 600)

        elapsed = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Retrieved ratings for user {user_id} in {elapsed:.2f}ms")

        return self.success_response(data=response_data)

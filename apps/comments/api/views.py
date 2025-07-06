import uuid
from rest_framework import permissions, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

import logging

from apps.core.views import BaseViewSet

from ..models import UserRating
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.core.cache import cache

User = get_user_model()
from .serializers import (
    RatingCreateSerializer,
    RatingDetailSerializer,
    RatingListSerializer,
    RatingEligibilitySerializer,
    BuyerSellerEligibilitySerializer,
    RatingStatsSerializer,
    PendingRatingSerializer,
)
from ..services import RatingService
from .permissions import CanRateTransactionPermission
from .throttling import RatingCreateThrottle, RatingViewThrottle
from apps.core.utils.cache_manager import CacheKeyManager
from .schema import (
    RATING_CREATE_SCHEMA,
    RATING_GIVEN_SCHEMA,
    RATING_LIST_SCHEMA,
    # RATING_DETAIL_SCHEMA,
    RATING_ELIGIBILITY_SCHEMA,
    RATING_STATS_SCHEMA,
    RATING_PENDING_SCHEMA,
    # RATING_GIVEN_SCHEMA,
    RATING_RECEIVED_SCHEMA,
    RatingSchemas,
)

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

    @RATING_CREATE_SCHEMA
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

    @RATING_LIST_SCHEMA
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
    @RATING_ELIGIBILITY_SCHEMA
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
    @RATING_STATS_SCHEMA
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
    @RATING_PENDING_SCHEMA
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
    @RATING_GIVEN_SCHEMA
    def given(self, request):
        """List ratings given by authenticated user"""
        queryset = RatingService.get_user_given_ratings(request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = RatingDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = RatingDetailSerializer(queryset, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["get"])
    @RATING_RECEIVED_SCHEMA
    def received(self, request):
        """List ratings received by authenticated user"""
        queryset = RatingService.get_user_received_ratings(request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = RatingDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = RatingDetailSerializer(queryset, many=True)
        return Response(serializer.data)


class UserRatingsViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for handling user ratings:
    - GET /api/v1/users/{user_id}/ratings/ - List all ratings for a user
    - GET /api/v1/users/{user_id}/ratings/{rating_id}/ - Get specific rating
    """

    permission_classes = [permissions.AllowAny]
    lookup_field = "rating_id"
    lookup_url_kwarg = "rating_id"

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "list":
            return RatingListSerializer
        return RatingDetailSerializer

    def get_queryset(self):
        """Get queryset based on user_id and optional rating_id"""
        user_id = self.kwargs.get("user_id")
        rating_id = self.kwargs.get("rating_id")

        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return UserRating.objects.none()

        # Base queryset for the user
        queryset = UserRating.objects.filter(user_id=user_uuid)

        # If rating_id is provided, filter further
        if rating_id:
            try:
                rating_uuid = uuid.UUID(rating_id)
                queryset = queryset.filter(id=rating_uuid)
            except (ValueError, TypeError):
                return UserRating.objects.none()

        return queryset

    def validate_user_id(self, user_id):
        """Validate user_id format and existence"""
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            return False, Response(
                {"error": "user_id must be a valid UUID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Optional: Check if user exists
        if not User.objects.filter(id=user_uuid).exists():
            return False, Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return True, user_uuid

    def validate_rating_id(self, rating_id):
        """Validate rating_id format"""
        try:
            rating_uuid = uuid.UUID(rating_id)
            return True, rating_uuid
        except (ValueError, TypeError):
            return False, Response(
                {"error": "rating_id must be a valid UUID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @RatingSchemas.LIST_USER_RATINGS
    def list(self, request, *args, **kwargs):
        """List all ratings for a specific user"""
        user_id = self.kwargs.get("user_id")

        # Validate user_id
        is_valid, result = self.validate_user_id(user_id)
        if not is_valid:
            return result

        user_uuid = result

        # Get page number
        page_num = request.query_params.get("page", 1)

        # Check cache first
        cache_key = CacheKeyManager.make_key(
            "rating", "list", user_id=user_id, page=page_num
        )
        cached_data = CacheKeyManager.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Get ratings using service
        try:
            queryset, total_count = RatingService.get_user_ratings_list(
                user_id=user_uuid, page=page_num, use_cache=False
            )
        except Exception as e:
            return Response(
                {"error": "Failed to fetch ratings"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Paginate and serialize
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)

            # Cache the result
            CacheKeyManager.set(cache_key, paginated_response.data)
            return paginated_response

        # No pagination
        serializer = self.get_serializer(queryset, many=True)
        response_data = serializer.data

        # Cache the result
        CacheKeyManager.set(cache_key, response_data)

        return Response(response_data)

    @RatingSchemas.RETRIEVE_USER_RATING
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a specific rating for a user"""
        user_id = self.kwargs.get("user_id")
        rating_id = self.kwargs.get("rating_id")

        # Validate user_id
        is_valid, result = self.validate_user_id(user_id)
        if not is_valid:
            return result

        user_uuid = result

        # Validate rating_id
        is_valid, result = self.validate_rating_id(rating_id)
        if not is_valid:
            return result

        rating_uuid = result

        # Check cache first
        cache_key = CacheKeyManager.make_key(
            "rating", "detail", user_id=user_id, rating_id=rating_id
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Get the specific rating
        try:
            rating = get_object_or_404(UserRating, id=rating_uuid, user_id=user_uuid)
        except UserRating.DoesNotExist:
            return Response(
                {"error": "Rating not found for this user"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Serialize and return
        serializer = self.get_serializer(rating)
        response_data = serializer.data

        # Cache the result
        cache.set(cache_key, response_data)

        return Response(response_data)

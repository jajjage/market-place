import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.core.views import BaseViewSet
from apps.core.utils.cache_manager import CacheKeyManager, CacheManager
from apps.products.product_base.models import Product
from apps.products.product_negotiation.models import (
    PriceNegotiation,
    NegotiationHistory,
)
from apps.products.product_negotiation.services import (
    NegotiationService,
    NegotiationAnalyticsService,
    NegotiationNotificationService,
)
from apps.products.product_negotiation.serializers import (
    NegotiationResponseSerializer,
    InitiateNegotiationSerializer,
    PriceNegotiationSerializer,
    NegotiationStatsSerializer,
    UserNegotiationHistorySerializer,
)
from apps.products.product_negotiation.utils.rate_limiting import (
    NegotiationInitiateRateThrottle,
    NegotiationRateThrottle,
    NegotiationRespondRateThrottle,
)
from apps.products.product_variant.models import ProductVariant

logger = logging.getLogger("negotiation_performance")


class ProductNegotiationViewSet(BaseViewSet):
    """Enhanced negotiation viewset with caching and rate limiting"""

    queryset = PriceNegotiation.objects.all()
    serializer_class = PriceNegotiationSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [NegotiationRateThrottle]

    logger = logging.getLogger("negotiation_performance")

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        if not self.request.user.is_authenticated:
            return PriceNegotiation.objects.none()

        # Users can only see negotiations they're involved in
        return (
            PriceNegotiation.objects.filter(
                Q(buyer=self.request.user) | Q(seller=self.request.user)
            )
            .select_related("product", "buyer", "seller")
            .prefetch_related("history")
        )

    @action(
        detail=False,
        url_path=r"initiate-negotiation",
        methods=["post"],
        throttle_classes=[NegotiationInitiateRateThrottle],
    )
    def initiate_negotiation(self, request):
        """
        Initiate a price negotiation for a product.
        Enhanced with caching, validation, and rate limiting.
        """
        start_time = timezone.now()
        variant_id = request.data.get("variant_id")
        if not variant_id:
            return self.error_response(
                message="You must Provide variant id",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Validate request data
        serializer = InitiateNegotiationSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
            )

        variant = get_object_or_404(ProductVariant, id=variant_id)
        offered_price = serializer.validated_data["offered_price"]
        notes = serializer.validated_data.get("notes", "")

        # Use service to initiate negotiation
        success, result = NegotiationService.initiate_negotiation(
            variant=variant,
            buyer=request.user,
            offered_price=offered_price,
            notes=notes,
        )

        if not success:
            return self.error_response(
                message=result["errors"], status_code=status.HTTP_400_BAD_REQUEST
            )

        negotiation = result["negotiation"]
        created = result["created"]

        # Send notification
        NegotiationNotificationService.notify_seller_response(negotiation)

        # Serialize response
        response_serializer = PriceNegotiationSerializer(
            negotiation, context={"request": request}
        )

        duration = (timezone.now() - start_time).total_seconds() * 1000
        self.logger.info(f"Negotiation initiated in {duration:.2f}ms")

        return self.success_response(
            data={
                "message": result["message"],
                "negotiation": response_serializer.data,
                "created": created,
            },
            status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="respond",
        throttle_classes=[NegotiationRespondRateThrottle],
    )
    def respond_to_negotiation(self, request, pk=None):
        """
        Unified endpoint for both buyers and sellers to respond to negotiations.
        Handles accept, reject, and counter responses.
        """
        start_time = timezone.now()

        # Get negotiation with related objects
        negotiation = get_object_or_404(
            PriceNegotiation.objects.select_related("product", "buyer", "seller"),
            id=pk,
        )

        # Validate request data
        serializer = NegotiationResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
            )

        # Extract validated data
        response_type = serializer.validated_data["response_type"]
        counter_price = serializer.validated_data.get("counter_price")
        notes = serializer.validated_data.get("notes", "")

        # Use unified service method
        success, result = NegotiationService.respond_to_negotiation(
            negotiation=negotiation,
            user=request.user,
            response_type=response_type,
            counter_price=counter_price,
            notes=notes,
        )

        if not success:
            return self.error_response(
                message=result["errors"], status_code=status.HTTP_400_BAD_REQUEST
            )

        # Serialize response
        updated_negotiation = result["negotiation"]
        response_serializer = PriceNegotiationSerializer(
            updated_negotiation, context={"request": request}
        )

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Negotiation response processed in {duration:.2f}ms")

        return self.success_response(
            data=response_serializer.data,
            message=result["message"],
        )

    # Keep these methods for backward compatibility if needed
    @action(
        detail=True,
        methods=["post"],
        url_path="seller-respond",
        throttle_classes=[NegotiationRespondRateThrottle],
    )
    def seller_respond(self, request, pk=None):
        """Seller-specific endpoint (delegates to unified method)"""
        return self.respond_to_negotiation(request, pk)

    @action(
        detail=True,
        methods=["post"],
        url_path="buyer-respond",
    )
    def buyer_respond(self, request, pk=None):
        """Buyer-specific endpoint (delegates to unified method)"""
        return self.respond_to_negotiation(request, pk)

    @action(detail=False, methods=["get"])
    def my_negotiations(self, request):
        """
        Get current user's negotiations with caching and filtering options.
        """
        start_time = timezone.now()

        # Get query parameters
        status_filter = request.query_params.get("status")
        role_filter = request.query_params.get("role")  # 'buyer' or 'seller'
        product_id = request.query_params.get("product_id")

        # Build cache key
        cache_key = CacheKeyManager.make_key(
            "negotiation",
            "user_list",
            user_id=request.user.id,
            status=status_filter or "all",
            role=role_filter or "all",
            product=product_id or "all",
        )

        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Build queryset
        queryset = self.get_queryset()

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if role_filter == "buyer":
            queryset = queryset.filter(buyer=request.user)
        elif role_filter == "seller":
            queryset = queryset.filter(seller=request.user)

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # Order by most recent
        queryset = queryset.order_by("-updated_at")

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            result = self.get_paginated_response(serializer.data)

            # Cache for 5 minutes
            cache.set(cache_key, result.data, 300)

            duration = (timezone.now() - start_time).total_seconds() * 1000
            self.logger.info(f"User negotiations fetched in {duration:.2f}ms")

            return result

        serializer = self.get_serializer(queryset, many=True)
        response_data = {"results": serializer.data, "count": len(serializer.data)}

        # Cache for 5 minutes
        cache.set(cache_key, response_data, 300)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        self.logger.info(f"User negotiations fetched in {duration:.2f}ms")

        return Response(response_data)

    @action(detail=False, url_path=r"stats/(?P<product_id>[^/.]+)", methods=["get"])
    def product_stats(self, request, product_id=None):
        """
        Get negotiation statistics for a specific product.
        """
        start_time = timezone.now()

        product = get_object_or_404(Product, id=product_id)

        # Check if user has permission to view stats (product owner or admin)
        if product.seller != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You don't have permission to view these statistics."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get stats using service
        stats = NegotiationAnalyticsService.get_negotiation_stats(product)

        # Serialize response
        serializer = NegotiationStatsSerializer(stats)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        self.logger.info(f"Product negotiation stats fetched in {duration:.2f}ms")

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def my_history(self, request):
        """
        Get user's negotiation history with caching.
        """
        start_time = timezone.now()

        limit = int(request.query_params.get("limit", 20))
        limit = min(limit, 100)  # Cap at 100

        # Get history using service
        history = NegotiationAnalyticsService.get_user_negotiation_history(
            request.user, limit=limit
        )

        # Serialize response
        serializer = UserNegotiationHistorySerializer(history, many=True)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        self.logger.info(f"User negotiation history fetched in {duration:.2f}ms")

        return Response({"results": serializer.data, "count": len(serializer.data)})

    @action(
        detail=False, url_path=r"cancel/(?P<negotiation_id>[^/.]+)", methods=["post"]
    )
    def cancel_negotiation(self, request, negotiation_id=None):
        """
        Cancel an active negotiation.
        """
        start_time = timezone.now()

        negotiation = get_object_or_404(PriceNegotiation, id=negotiation_id)

        # Check permissions (buyer or seller can cancel)
        if request.user not in [negotiation.buyer, negotiation.seller]:
            return Response(
                {"detail": "You don't have permission to cancel this negotiation."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if negotiation can be cancelled
        if negotiation.status not in ["pending", "countered"]:
            return Response(
                {
                    "detail": f"Cannot cancel negotiation with status '{negotiation.status}'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cancel the negotiation
        negotiation.status = "rejected"
        negotiation.save()

        # Record in history
        role = "buyer" if request.user == negotiation.buyer else "seller"
        NegotiationHistory.objects.create(
            negotiation=negotiation,
            action="price_rejected",
            user=request.user,
            notes=f"Negotiation cancelled by {role}",
        )

        # Invalidate cache
        CacheManager.invalidate("negotiation", id=negotiation.id)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        self.logger.info(f"Negotiation cancelled in {duration:.2f}ms")

        return Response(
            {
                "message": "Negotiation cancelled successfully",
                "negotiation_id": negotiation.id,
            }
        )

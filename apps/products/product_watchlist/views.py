from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from drf_spectacular.utils import extend_schema, OpenApiParameter


from apps.core.views import BaseViewSet
from .serializers import (
    ProductWatchlistItemListSerializer,
    ProductWatchlistItemDetailSerializer,
    ProductWatchlistBulkSerializer,
    WatchlistStatsSerializer,
)
from .services import WatchlistService, CACHE_TTL
from .utils.rate_limiting import (
    AdminWatchlistThrottle,
    WatchlistBulkThrottle,
    WatchlistRateThrottle,
    WatchlistToggleThrottle,
)


class ProductWatchlistViewSet(BaseViewSet):
    """
    API endpoint for managing product watchlist items.
    Allows users to create and manage their product watchlists.
    """

    throttle_classes = [WatchlistRateThrottle]
    permission_classes = []
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["added_at"]
    ordering = ["-added_at"]

    def get_queryset(self):
        """
        Return optimized watchlist items for the current user.
        """
        user = self.request.user
        user_id = None

        if user.is_staff and "user_id" in self.request.query_params:
            try:
                user_id = int(self.request.query_params.get("user_id"))
            except (ValueError, TypeError):
                pass

        return WatchlistService.get_user_watchlist_queryset(user, user_id)

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_mapping = {
            "list": ProductWatchlistItemListSerializer,
            "bulk_operation": ProductWatchlistBulkSerializer,
            "stats": WatchlistStatsSerializer,
        }
        return serializer_mapping.get(self.action, ProductWatchlistItemDetailSerializer)

    def get_throttles(self):
        # Use custom throttles for specific actions, else default
        if self.action == "bulk_operation":
            throttle_classes = [WatchlistBulkThrottle]
        elif self.action == "toggle_product":
            throttle_classes = [WatchlistToggleThrottle]
        elif self.action == "by_product":
            throttle_classes = [AdminWatchlistThrottle]
        else:
            throttle_classes = self.throttle_classes
        return [throttle() for throttle in throttle_classes]

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        """Get user's watchlist with caching."""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=ProductWatchlistBulkSerializer,
        responses={200: {"description": "Bulk operation completed successfully"}},
    )
    @action(detail=False, methods=["post"])
    def bulk_operation(self, request):
        """Perform bulk operations (add/remove) on watchlist items."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        if isinstance(result, list):
            response_data = {
                "message": f"Added {len(result)} products to your watchlist",
                "added_count": len(result),
                "operation": "add",
            }
        elif isinstance(result, dict) and "removed_count" in result:
            response_data = {
                "message": f"Removed {result['removed_count']} products from your watchlist",
                "removed_count": result["removed_count"],
                "operation": "remove",
            }
        else:
            response_data = result

        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: WatchlistStatsSerializer})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get statistics about the user's watchlist with caching."""
        user = request.user
        user_id = None

        if user.is_staff and "user_id" in self.request.query_params:
            try:
                user_id = int(self.request.query_params.get("user_id"))
            except (ValueError, TypeError):
                pass

        stats = WatchlistService.get_watchlist_stats(user, user_id)
        serializer = self.get_serializer(stats)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Product ID to check",
                required=True,
                type=int,
            )
        ]
    )
    @action(detail=False, methods=["get"])
    def check_product(self, request):
        """Check if a product is in the user's watchlist with caching."""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid product_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_in_watchlist = WatchlistService.is_product_in_watchlist(
            request.user, product_id
        )

        return Response({"in_watchlist": is_in_watchlist})

    @extend_schema(
        request={
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        }
    )
    @action(detail=False, methods=["post"])
    def toggle_product(self, request):
        """Toggle a product in the user's watchlist."""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid product_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = WatchlistService.toggle_product_in_watchlist(request.user, product_id)

        response_status = (
            status.HTTP_201_CREATED
            if result["status"] == "added"
            else status.HTTP_200_OK
        )

        return Response(result, status=response_status)

    @action(detail=False, methods=["get"])
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Filter by product ID",
                required=True,
                type=int,
            )
        ]
    )
    def by_product(self, request):
        """Get watchlist count for a specific product (Staff only) with caching."""
        if not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN
            )

        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid product_id format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        count = WatchlistService.get_product_watchlist_count(product_id)

        return Response({"product_id": product_id, "watchlist_count": count})

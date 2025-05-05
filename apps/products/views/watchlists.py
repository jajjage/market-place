from rest_framework import permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.views import BaseViewSet
from apps.products.models import ProductWatchlistItem, Product
from apps.products.serializers import (
    ProductWatchlistItemListSerializer,
    ProductWatchlistItemDetailSerializer,
    ProductWatchlistItemCreateSerializer,
    ProductWatchlistBulkSerializer,
    WatchlistStatsSerializer,
)


class ProductWatchlistViewSet(BaseViewSet):
    """
    API endpoint for managing product watchlist items.
    Allows users to create and manage their product watchlists.
    """

    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["added_at"]
    ordering = ["-added_at"]

    def get_queryset(self):
        """
        Return watchlist items for the current user.
        Staff users can filter by user_id to see other users' watchlists.
        """
        user = self.request.user

        # Base queryset (either user's own watchlist or all for staff)
        if user.is_staff and "user_id" in self.request.query_params:
            try:
                user_id = int(self.request.query_params.get("user_id"))
                return ProductWatchlistItem.objects.filter(user_id=user_id)
            except (ValueError, TypeError):
                pass

        # Default to current user's watchlist
        return ProductWatchlistItem.objects.filter(user=user)

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return ProductWatchlistItemListSerializer
        elif self.action == "create":
            return ProductWatchlistItemCreateSerializer
        elif self.action == "bulk_operation":
            return ProductWatchlistBulkSerializer
        elif self.action == "stats":
            return WatchlistStatsSerializer
        return ProductWatchlistItemDetailSerializer

    def get_permissions(self):
        """
        Custom permissions:
        - Users can only access their own watchlists
        - Staff users can view any watchlist
        """
        permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """Create a new watchlist item for the current user."""
        serializer.save()

    @extend_schema(
        request=ProductWatchlistBulkSerializer,
        responses={200: {"description": "Bulk operation completed successfully"}},
    )
    @action(detail=False, methods=["post"])
    def bulk_operation(self, request):
        """
        Perform bulk operations (add/remove) on watchlist items.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.save()

        if isinstance(result, list):
            # For bulk add operations
            response_data = {
                "message": f"Added {len(result)} products to your watchlist",
                "added_count": len(result),
            }
        elif isinstance(result, dict) and "removed_count" in result:
            # For bulk remove operations
            response_data = {
                "message": f"Removed {result['removed_count']} products from your watchlist",
                "removed_count": result["removed_count"],
            }
        else:
            # Default response
            response_data = result

        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: WatchlistStatsSerializer})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Get statistics about the user's watchlist.
        """
        # user = request.user
        queryset = self.get_queryset()

        # Total items in watchlist
        total_items = queryset.count()

        # Recently added items (IDs only)
        recently_added = list(
            queryset.order_by("-added_at")[:5].values_list("product_id", flat=True)
        )

        # Most watched categories
        category_counts = []
        if total_items > 0:
            category_counts = list(
                queryset.values("product__category__name")
                .annotate(count=Count("product__category"))
                .filter(product__category__isnull=False)
                .order_by("-count")[:5]
                .values("product__category__name", "count")
            )
            # Transform to the expected format
            category_counts = [
                {"name": item["product__category__name"], "count": item["count"]}
                for item in category_counts
            ]

        stats = {
            "total_items": total_items,
            "recently_added": recently_added,
            "most_watched_categories": category_counts,
        }

        serializer = self.get_serializer(stats)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def check_product(self, request):
        """
        Check if a product is in the user's watchlist.
        """
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_in_watchlist = ProductWatchlistItem.objects.filter(
            user=request.user, product_id=product_id
        ).exists()

        return Response({"in_watchlist": is_in_watchlist})

    @action(detail=False, methods=["post"])
    def toggle_product(self, request):
        """
        Toggle a product in the user's watchlist (add if not present, remove if present).
        """
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Check if product exists and is active
        product = get_object_or_404(Product, id=product_id, is_active=True)

        # Check if product is already in watchlist
        watchlist_item = ProductWatchlistItem.objects.filter(
            user=request.user, product=product
        ).first()

        if watchlist_item:
            # Remove from watchlist
            watchlist_item.delete()
            return Response(
                {"status": "removed", "message": "Product removed from watchlist"}
            )
        else:
            # Add to watchlist
            watchlist_item = ProductWatchlistItem.objects.create(
                user=request.user, product=product
            )
            return Response(
                {"status": "added", "message": "Product added to watchlist"},
                status=status.HTTP_201_CREATED,
            )

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
        """
        Get watchlist count for a specific product.
        Staff only endpoint.
        """
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

        count = ProductWatchlistItem.objects.filter(product_id=product_id).count()

        return Response({"product_id": product_id, "watchlist_count": count})

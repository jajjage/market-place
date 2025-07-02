from rest_framework import status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from django.utils import timezone
import logging

from apps.core.utils.extract_error import extract_validation_error_message
from apps.core.views import BaseViewSet
from apps.products.product_watchlist.utils.exceptions import (
    WatchlistError,
    WatchlistValidationError,
)
from .serializers import (
    ProductWatchlistItemCreateSerializer,
    ProductWatchlistItemListSerializer,
    ProductWatchlistItemDetailSerializer,
    ProductWatchlistBulkSerializer,
    WatchlistStatsSerializer,
    WatchlistInsightsSerializer,
    WatchlistOperationResultSerializer,
)
from .services import WatchlistService
from .utils.rate_limiting import (
    AdminWatchlistThrottle,
    WatchlistBulkThrottle,
    WatchlistRateThrottle,
    WatchlistToggleThrottle,
)

logger = logging.getLogger(__name__)


class ProductWatchlistViewSet(BaseViewSet):
    """
    Enhanced API endpoint for managing product watchlist items.

    Provides full CRUD operations, bulk operations, statistics, and insights
    for user watchlists with proper error handling, caching, and validation.
    """

    throttle_classes = [WatchlistRateThrottle]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ["added_at", "product__name", "product__price"]
    ordering = ["-added_at"]
    search_fields = ["product__name", "product__category__name"]

    def get_queryset(self):
        """
        Return optimized watchlist items for the current user with proper error handling.
        """
        try:
            user = self.request.user
            target_user_id = None

            # Handle staff user operations
            if user.is_staff and "user_id" in self.request.query_params:
                target_user_id = self.request.query_params.get("user_id")
            return WatchlistService.get_user_watchlist_queryset(user, target_user_id)

        except Exception as e:
            logger.error(f"Error in get_queryset: {e}")
            return self.get_serializer().Meta.model.objects.none()

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_mapping = {
            "list": ProductWatchlistItemListSerializer,
            "create": ProductWatchlistItemCreateSerializer,
            "bulk_operation": ProductWatchlistBulkSerializer,
            "stats": WatchlistStatsSerializer,
            "insights": WatchlistInsightsSerializer,
            "toggle_product": WatchlistOperationResultSerializer,
        }
        return serializer_mapping.get(self.action, ProductWatchlistItemDetailSerializer)

    def get_throttles(self):
        """Apply appropriate throttling based on action."""
        throttle_mapping = {
            "bulk_operation": [WatchlistBulkThrottle],
            "toggle_product": [WatchlistToggleThrottle],
            "by_product": [AdminWatchlistThrottle],
            "stats": [WatchlistRateThrottle],
            "insights": [WatchlistRateThrottle],
        }

        throttle_classes = throttle_mapping.get(self.action, self.throttle_classes)
        return [throttle() for throttle in throttle_classes]

    def handle_exception(self, exc):
        """Custom exception handling for watchlist operations."""
        if isinstance(exc, WatchlistValidationError):
            return Response(
                {"error": str(exc), "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif isinstance(exc, WatchlistError):
            return Response(
                {"error": str(exc), "code": "watchlist_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Log unexpected errors
        logger.error(f"Unexpected error in watchlist operation: {exc}")
        return super().handle_exception(exc)

    @extend_schema(
        summary="List user's watchlist items",
        description="Retrieve paginated list of watchlist items with optional filtering and sorting",
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="User ID (staff only)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="search",
                description="Search in product names and categories",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="ordering",
                description="Order by: added_at, -added_at, product__name, product__price",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: ProductWatchlistItemListSerializer(many=True),
            400: OpenApiResponse(description="Invalid parameters"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    def list(self, request, *args, **kwargs):
        """Get user's watchlist with enhanced filtering and caching."""
        try:
            # Validate staff operations
            if not request.user.is_staff and "user_id" in request.query_params:
                return self.error_response(
                    message="Permission denied. Staff access required.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            response = super().list(request, *args, **kwargs)

            # Add metadata to response
            if hasattr(response, "data") and isinstance(response.data, dict):
                response.data["metadata"] = {
                    "total_items": self.get_queryset().count(),
                    "filtered": bool(request.query_params.get("search")),
                    "user_id": (
                        request.query_params.get("user_id")
                        if request.user.is_staff
                        else None
                    ),
                }

            return response

        except Exception as e:
            logger.error(f"Error in watchlist list view: {e}")
            return Response(
                {"error": "Failed to retrieve watchlist"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Add product to watchlist",
        request=ProductWatchlistItemCreateSerializer,
        responses={
            201: ProductWatchlistItemDetailSerializer,
            400: OpenApiResponse(
                description="Invalid data or product already in watchlist"
            ),
            404: OpenApiResponse(description="Product not found"),
        },
    )
    def create(self, request, *args, **kwargs):
        """Add a single product to watchlist with validation."""
        try:
            logger.info(
                f"User {request.user.id} is attempting to add a product to watchlist"
            )

            # Validate the input data
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Get the validated product_id
            product_id = serializer.validated_data["product_id"]

            # Check if already in watchlist
            if (
                self.get_queryset()
                .filter(product_id=product_id, user=request.user)
                .exists()
            ):
                return self.error_response(
                    message="Product is already in your watchlist",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Add to watchlist using service
            result = WatchlistService.add_product_to_watchlist(  # Use add_product instead of toggle
                request.user, product_id
            )

            if not result.success:
                return self.error_response(
                    message={"error": result.message, "details": result.errors},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Get the created instance
            instance = (
                self.get_queryset()
                .filter(product_id=product_id, user=request.user)
                .first()
            )

            logger.info(
                f"Product {product_id} added to watchlist for user {request.user.id}"
            )

            if instance:
                result_serializer = ProductWatchlistItemDetailSerializer(instance)
                return self.success_response(
                    data=result_serializer.data, status_code=status.HTTP_201_CREATED
                )

            return self.success_response(
                data="Product added to watchlist successfully",
                status_code=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Error creating watchlist item: {e.args}")
            err_msg = extract_validation_error_message(e)
            return self.error_response(
                message=f"Failed to add product to watchlist: {err_msg}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Bulk watchlist operations",
        description="Add or remove multiple products from watchlist in a single operation",
        request=ProductWatchlistBulkSerializer,
        responses={
            200: WatchlistOperationResultSerializer,
            400: OpenApiResponse(description="Invalid operation or data"),
        },
    )
    @action(detail=False, methods=["post"])
    def bulk_operation(self, request):
        """Perform bulk operations (add/remove) on watchlist items."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            operation = serializer.validated_data["operation"]
            product_ids = serializer.validated_data["product_ids"]

            # Perform bulk operation using service
            if operation == "add":
                result = WatchlistService.bulk_add_products(request.user, product_ids)
            elif operation == "remove":
                result = WatchlistService.bulk_remove_products(
                    request.user, product_ids
                )
            else:
                return Response(
                    {"error": "Invalid operation. Must be 'add' or 'remove'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Serialize result
            result_serializer = WatchlistOperationResultSerializer(result)
            response_status = (
                status.HTTP_200_OK if result.success else status.HTTP_400_BAD_REQUEST
            )

            return Response(result_serializer.data, status=response_status)

        except Exception as e:
            logger.error(f"Error in bulk operation: {e}")
            return Response(
                {"error": "Failed to perform bulk operation"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get watchlist statistics",
        description="Retrieve comprehensive statistics about user's watchlist",
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="User ID (staff only)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="force_refresh",
                description="Force refresh cache",
                required=False,
                type=bool,
            ),
        ],
        responses={
            200: WatchlistStatsSerializer,
            400: OpenApiResponse(description="Invalid user_id parameter"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get statistics about the user's watchlist with caching."""
        try:
            user = request.user
            target_user_id = None
            force_refresh = (
                request.query_params.get("force_refresh", "").lower() == "true"
            )

            # Handle staff operations with proper validation
            if user.is_staff and "user_id" in request.query_params:
                target_user_id = request.query_params.get("user_id")

            elif "user_id" in request.query_params:
                # Non-staff user trying to access other user's data
                return self.error_response(
                    message="Permission denied. Staff access required.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            # Get stats using service
            stats = WatchlistService.get_watchlist_stats(
                user, target_user_id, force_refresh
            )
            serializer = self.get_serializer(stats)

            return self.success_response(
                data=serializer.data, status_code=status.HTTP_200_OK
            )

        except WatchlistValidationError as e:
            return self.error_response(
                message=f"{str(e)}, validation_error",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error getting watchlist stats: {e}")
            return self.error_response(
                message="Failed to retrieve watchlist statistics.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get watchlist insights",
        description="Get advanced analytics and insights about user's watchlist behavior",
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="User ID (staff only)",
                required=False,
                type=str,
            ),
        ],
        responses={
            200: WatchlistInsightsSerializer,
            400: OpenApiResponse(description="Invalid parameters"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    @action(detail=False, methods=["get"])
    def insights(self, request):
        """Get advanced insights about the user's watchlist."""
        try:
            user = request.user
            target_user_id = None

            # Handle staff operations
            if user.is_staff and "user_id" in request.query_params:
                target_user_id = request.query_params.get("user_id")

            elif "user_id" in request.query_params:
                return self.error_response(
                    message="Permission denied", status_code=status.HTTP_403_FORBIDDEN
                )

            insights = WatchlistService.get_watchlist_insights(user, target_user_id)
            serializer = self.get_serializer(insights)

            return self.success_response(
                data=serializer.data, status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error getting watchlist insights: {e}")
            return self.error_response(
                message="Failed to retrieve insights",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Check if product is in watchlist",
        description="Check if a specific product is in the user's watchlist",
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Product ID to check",
                required=True,
                type=str,
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {"in_watchlist": {"type": "boolean"}},
            },
            400: OpenApiResponse(description="Invalid or missing product_id"),
        },
    )
    @action(detail=False, methods=["get"])
    def check_product(self, request):
        """Check if a product is in the user's watchlist with caching."""
        try:
            product_id = request.query_params.get("product_id")
            if not product_id:
                return Response(
                    {"error": "product_id parameter is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate product_id format
            try:
                if not product_id.replace("-", "").replace("_", "").isalnum():
                    raise ValueError("Invalid format")
            except (ValueError, AttributeError):
                return self.error_response(
                    message="Invalid product_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            is_in_watchlist = WatchlistService.is_product_in_watchlist(
                request.user, product_id
            )

            return self.success_response(
                data={"in_watchlist": is_in_watchlist, "product_id": product_id}
            )

        except Exception as e:
            logger.error(f"Error checking product in watchlist: {e}")
            return self.error_response(
                message="Failed to check product status",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Toggle product in watchlist",
        description="Add or remove a product from watchlist (toggle operation)",
        request={
            "type": "object",
            "properties": {"product_id": {"type": "string", "format": "uuid"}},
            "required": ["product_id"],
        },
        responses={
            200: WatchlistOperationResultSerializer,
            201: WatchlistOperationResultSerializer,
            400: OpenApiResponse(description="Invalid product_id or operation failed"),
            404: OpenApiResponse(description="Product not found"),
        },
    )
    @action(detail=False, methods=["post"])
    def toggle_product(self, request):
        """Toggle a product in the user's watchlist."""
        try:
            product_id = request.data.get("product_id")
            if not product_id:
                return Response(
                    {"error": "product_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Use service for business logic
            result = WatchlistService.toggle_product_in_watchlist(
                request.user, product_id
            )

            # Serialize result
            serializer = WatchlistOperationResultSerializer(result)

            if not result.success:
                return Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)

            response_status = (
                status.HTTP_201_CREATED
                if result.status == "added"
                else status.HTTP_200_OK
            )

            return Response(serializer.data, status=response_status)

        except Exception as e:
            logger.error(f"Error toggling product in watchlist: {e}")
            return Response(
                {"error": "Failed to toggle product in watchlist"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get product watchlist count",
        description="Get total count of users who have this product in their watchlist (staff only)",
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Product ID to get count for",
                required=True,
                type=str,
            )
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "watchlist_count": {"type": "integer"},
                },
            },
            400: OpenApiResponse(description="Invalid product_id"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    @action(detail=False, methods=["get"])
    def by_product(self, request):
        """Get watchlist count for a specific product (Staff only) with caching."""
        try:
            if not request.user.is_staff:
                return self.error_response(
                    message="Permission denied. Staff access required.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            product_id = request.query_params.get("product_id")
            if not product_id:
                return self.error_response(
                    message="product_id parameter is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Validate product_id format
            try:
                if not product_id.replace("-", "").replace("_", "").isalnum():
                    raise ValueError("Invalid format")
            except (ValueError, AttributeError):
                return Response(
                    {"error": "Invalid product_id format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            count = WatchlistService.get_product_watchlist_count(product_id)

            return self.success_response(
                data={
                    "product_id": product_id,
                    "watchlist_count": count,
                    "timestamp": timezone.now().isoformat(),
                }
            )

        except Exception as e:
            logger.error(f"Error getting product watchlist count: {e}")
            return self.error_response(
                message="Failed to get product watchlist count",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Remove item from watchlist",
        description="Remove a specific watchlist item by ID",
        responses={
            204: OpenApiResponse(description="Item removed successfully"),
            404: OpenApiResponse(description="Item not found"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    @action(detail=False, methods=["post"])
    def remove_from_watchlist(self, request, *args, **kwargs):
        """Remove a watchlist item with proper validation."""
        try:
            product_id = request.data.get("product_id")
            if not product_id:
                return self.error_response(
                    message="product_id is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            result = WatchlistService.remove_product_from_watchlist(
                request.user, product_id
            )

            if not result.success:
                return self.error_response(
                    message=f"Failed to remove, {result.message}",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            return self.success_response(
                message=result.message, status_code=status.HTTP_204_NO_CONTENT
            )

        except Exception as e:
            logger.error(f"Error removing watchlist item: {e}")
            err_msg = extract_validation_error_message(e)
            return self.error_response(
                message=f"Failed to remove item from watchlist: {err_msg}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.views import BaseViewSet

from .utils.rate_limiting import ProductConditionRateThrottle
from .models import ProductCondition
from .services import (
    ProductConditionService,
    CACHE_TTL,
)
from .serializers import (
    ProductConditionListSerializer,
    ProductConditionDetailSerializer,
    ProductConditionWriteSerializer,
    ProductConditionAnalyticsSerializer,
    ConditionBulkOrderSerializer,
    ProductConditionBulkCreateSerializer,
)


class ProductConditionViewSet(BaseViewSet):
    """
    Enhanced API endpoint for managing product conditions.
    """

    queryset = ProductCondition.objects.filter(is_active=True)
    permission_classes = []
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "quality_score", "display_order", "created_at"]
    ordering = ["display_order", "name"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_map = {
            "list": ProductConditionListSerializer,
            "create": ProductConditionWriteSerializer,
            "update": ProductConditionWriteSerializer,
            "partial_update": ProductConditionWriteSerializer,
            "analytics": ProductConditionAnalyticsSerializer,
            "bulk_order": ConditionBulkOrderSerializer,
            "bulk_create": ProductConditionBulkCreateSerializer,
        }
        return serializer_map.get(self.action, ProductConditionDetailSerializer)

    def get_queryset(self):
        """Optimize queryset based on action."""
        queryset = super().get_queryset()

        if self.action == "list":
            return ProductConditionService.get_active_conditions(include_stats=True)
        elif self.action == "popular":
            return queryset  # Will be handled in the action

        return queryset.select_related("created_by")

    def get_throttles(self):
        if self.action == "create":
            throttle_classes = [ProductConditionRateThrottle]
        else:
            throttle_classes = []
        return [throttle() for throttle in throttle_classes]

    def perform_create(self, serializer):
        """
        Create or retrieve condition using service layer and attach the instance to the serializer.
        Do NOT call super().perform_create(serializer) here, as the service handles persistence.
        """
        # Call your service to create or get the condition
        condition = ProductConditionService.create_condition(
            serializer.validated_data, user=self.request.user
        )

        # Assign the created/retrieved instance to the serializer's instance attribute.
        # This is crucial so that serializer.data (used by DRF's create method)
        # will correctly reflect the object.
        serializer.instance = condition

        # You might also want to set the HTTP status code based on 'created'
        # if your service layer were to return that information.
        # For now, let's assume get_or_create logic in service is enough,
        # and the overarching DRF create method will return 201.
        # If you need different status codes (200 for existing, 201 for new),
        # you'd move the get_or_create logic directly into the view's `create` method
        # instead of `perform_create`.

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get only active product conditions."""
        conditions = ProductConditionService.get_active_conditions(include_stats=True)
        serializer = ProductConditionListSerializer(
            conditions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def popular(self, request):
        """Get most popular conditions."""
        limit = min(int(request.query_params.get("limit", 10)), 50)
        conditions = ProductConditionService.get_popular_conditions(limit)

        serializer = ProductConditionListSerializer(
            conditions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get products with this condition."""
        from apps.products.product_base.serializers import ProductListSerializer

        # Parse filters
        filters = {}
        for param in [
            "category",
            "price_min",
            "price_max",
            "brand",
            "in_stock",
            "rating_min",
        ]:
            if param in request.query_params:
                value = request.query_params[param]
                if param in ["price_min", "price_max", "rating_min"]:
                    try:
                        value = float(value)
                    except ValueError:
                        continue
                elif param == "in_stock":
                    value = value.lower() == "true"
                filters[param] = value

        result = ProductConditionService.get_condition_with_products(int(pk), filters)

        if not result:
            return Response(
                {"error": "Product condition not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Apply pagination
        products = result["products"]
        page = self.paginate_queryset(products)

        if page is not None:
            serializer = ProductListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(
            products, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def analytics(self, request, pk=None):
        """Get detailed analytics for a condition."""
        analytics = ProductConditionService.get_condition_analytics(int(pk))

        if not analytics:
            return Response(
                {"error": "Product condition not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProductConditionAnalyticsSerializer(analytics)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_quality(self, request):
        """Get conditions by quality score range."""
        min_score = int(request.query_params.get("min_score", 1))
        max_score = int(request.query_params.get("max_score", 10))

        conditions = ProductConditionService.get_conditions_by_quality_range(
            min_score, max_score
        )

        serializer = ProductConditionListSerializer(
            conditions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_order(self, request):
        """Bulk update display order for conditions."""
        serializer = ConditionBulkOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success = ProductConditionService.bulk_update_display_order(
            serializer.validated_data["conditions"]
        )

        if success:
            return Response({"message": "Display order updated successfully"})
        else:
            return Response(
                {"error": "Failed to update display order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create multiple conditions at once."""
        serializer = ProductConditionBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conditions = ProductConditionService.bulk_create_conditions(
            serializer.validated_data["conditions"],
            user=self.request.user,
        )

        response_serializer = ProductConditionListSerializer(
            conditions, many=True, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def suggest_price(self, request):
        """Suggest price based on condition and original price."""
        original_price = request.data.get("original_price")
        condition_id = request.data.get("condition_id")

        if not original_price or not condition_id:
            return Response(
                {"error": "original_price and condition_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            suggested_price = ProductConditionService.suggest_condition_price(
                float(original_price), int(condition_id)
            )

            return Response(
                {
                    "original_price": original_price,
                    "suggested_price": suggested_price,
                    "condition_id": condition_id,
                }
            )
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid price or condition ID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

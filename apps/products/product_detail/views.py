from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.core.throttle import ThrottledException
from .models import ProductDetail, ProductDetailTemplate
from .serializers import (
    ProductDetailSerializer,
    ProductDetailSummarySerializer,
    ProductDetailGroupedSerializer,
    ProductDetailTemplateSerializer,
    ProductDetailBulkCreateSerializer,
)
from .services import ProductDetailService


class ProductDetailViewSet(viewsets.ModelViewSet):
    """ViewSet for ProductDetail with caching and rate limiting"""

    serializer_class = ProductDetailSerializer
    lookup_field = "id"

    def get_throttles(self):
        """
        Apply custom throttles for list, retrieve, create, update, and partial_update actions.
        """
        from apps.products.product_detail.utils.rate_limiting import (
            ProductDetailListThrottle,
            ProductDetailRetrieveThrottle,
            ProductDetailWriteThrottle,
        )

        action = self.action if hasattr(self, "action") else None
        if action == "list":
            return [ProductDetailListThrottle()]
        elif action == "retrieve":
            return [ProductDetailRetrieveThrottle()]
        elif action in ["create", "update", "partial_update"]:
            return [ProductDetailWriteThrottle()]
        return super().get_throttles()

    def handle_exception(self, exc):
        """Custom exception handling for throttling."""
        if hasattr(exc, "default_code") and exc.default_code == "throttled":
            # Convert DRF throttled exception to custom one
            scope = (
                getattr(self.get_throttles()[0], "scope", None)
                if self.get_throttles()
                else None
            )
            raise ThrottledException(wait=exc.wait, scope=scope)
        return super().handle_exception(exc)

    def get_queryset(self):
        product_id = self.kwargs.get("product_pk")
        if product_id:
            return ProductDetail.objects.filter(
                product_id=product_id, is_active=True
            ).select_related("product", "template")
        return ProductDetail.objects.select_related("product", "template")

    def list(self, request, *args, **kwargs):
        """List product details with optional filtering"""
        product_id = self.kwargs.get("product_pk")
        detail_type = request.query_params.get("type")
        highlighted = request.query_params.get("highlighted") == "true"

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        details = ProductDetailService.get_product_details(
            product_id=product_id, detail_type=detail_type, highlighted_only=highlighted
        )

        serializer = self.get_serializer(details, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def grouped(self, request, *args, **kwargs):
        """Get details grouped by type"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        grouped_details = ProductDetailService.get_grouped_details(product_id)

        # Convert to list of tuples for serializer
        grouped_list = [
            (detail_type, details) for detail_type, details in grouped_details.items()
        ]

        serializer = ProductDetailGroupedSerializer(grouped_list, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def highlighted(self, request, *args, **kwargs):
        """Get only highlighted details"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        details = ProductDetailService.get_highlighted_details(product_id)
        serializer = ProductDetailSummarySerializer(details, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request, *args, **kwargs):
        """Bulk create product details"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        from apps.products.product_base.models import Product

        product = get_object_or_404(Product, id=product_id)

        serializer = ProductDetailBulkCreateSerializer(data=request.data)
        if serializer.is_valid():
            details = ProductDetailService.bulk_create_details(
                product=product, details_data=serializer.validated_data["details"]
            )

            response_serializer = ProductDetailSerializer(details, many=True)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        """Override to invalidate cache on update"""
        instance = serializer.save()
        from apps.core.utils.cache_manager import CacheManager

        CacheManager.invalidate("product_detail", product_id=instance.product_id)

    def perform_destroy(self, instance):
        """Soft delete instead of hard delete"""
        ProductDetailService.delete_detail(instance.id)


class ProductDetailTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ProductDetail templates (admin-created)"""

    queryset = ProductDetailTemplate.objects.all()
    serializer_class = ProductDetailTemplateSerializer

    @action(detail=False, methods=["get"])
    def for_category(self, request):
        """Get templates available for a specific category"""
        category_id = request.query_params.get("category_id")

        templates = ProductDetailService.get_templates_for_category(
            category_id=category_id if category_id else None
        )

        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)

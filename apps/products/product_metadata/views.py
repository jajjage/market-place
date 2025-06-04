from rest_framework import permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.views import BaseViewSet
from apps.products.product_base.models import Product
from .models import ProductMeta
from .serializers import (
    ProductMetaSerializer,
    ProductMetaWriteSerializer,
    ProductMetaStatsSerializer,
    ProductMetaUpdateViewsSerializer,
    FeaturedProductMetaSerializer,
)


class ProductMetaViewSet(BaseViewSet):
    """
    API endpoint for managing product metadata.
    Supports CRUD operations and specialized endpoints for featured products and view tracking.
    """

    queryset = ProductMeta.objects.all()
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["views_count", "created_at", "featured"]
    ordering = ["-featured", "-views_count"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return ProductMetaWriteSerializer
        elif self.action == "stats":
            return ProductMetaStatsSerializer
        elif self.action == "increment_view":
            return ProductMetaUpdateViewsSerializer
        elif self.action == "featured":
            return FeaturedProductMetaSerializer
        return ProductMetaSerializer

    def get_permissions(self):
        """
        Custom permissions:
        - List/retrieve/stats/featured/by_product: Anyone can view metadata
        - Create/update/delete: Only staff/admin users
        - Increment view: Anyone can increment view count
        """
        if self.action in ["list", "retrieve", "stats", "featured", "by_product"]:
            permission_classes = [permissions.AllowAny]
        elif self.action == "increment_view":
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    @extend_schema(responses={200: ProductMetaStatsSerializer(many=True)})
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """
        Get product metadata statistics.
        Returns view counts and other statistics for products.
        """
        # Optional filtering by views threshold
        min_views = request.query_params.get("min_views", 0)
        try:
            min_views = int(min_views)
        except ValueError:
            min_views = 0

        # Get metadata filtered by minimum views
        queryset = self.get_queryset().filter(views_count__gte=min_views)

        # Apply optional sorting
        sort_by = request.query_params.get("sort", "-views_count")
        if sort_by not in ["views_count", "-views_count", "created_at", "-created_at"]:
            sort_by = "-views_count"
        queryset = queryset.order_by(sort_by)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(responses={200: ProductMetaUpdateViewsSerializer})
    @action(detail=True, methods=["post"])
    def increment_view(self, request, pk=None):
        """
        Increment the view count for a product.
        """
        instance = self.get_object()

        # Update the view count using F expression to avoid race conditions
        ProductMeta.objects.filter(pk=instance.pk).update(
            views_count=F("views_count") + 1
        )

        # Refresh the instance from the database
        instance.refresh_from_db()

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(
        responses={200: FeaturedProductMetaSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="limit",
                description="Number of featured products to return",
                required=False,
                type=int,
            )
        ],
    )
    @action(detail=False, methods=["get"])
    def featured(self, request):
        """
        Get featured products metadata.
        Returns metadata for products marked as featured.
        """
        # Get limit parameter with default value
        try:
            limit = int(request.query_params.get("limit", 10))
        except ValueError:
            limit = 10

        # Get featured products
        queryset = (
            self.get_queryset().filter(featured=True).order_by("-views_count")[:limit]
        )

        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        responses={200: ProductMetaSerializer},
        parameters=[
            OpenApiParameter(
                name="product_id", description="Product ID", required=True, type=int
            )
        ],
    )
    @action(detail=False, methods=["get"])
    def by_product(self, request):
        """
        Get metadata for a specific product.
        """
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = get_object_or_404(Product, pk=product_id)

        # Get or create metadata for the product
        meta, created = ProductMeta.objects.get_or_create(product=product)

        serializer = ProductMetaSerializer(meta, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def popular(self, request):
        """
        Get most popular products based on view count.
        """
        limit = int(request.query_params.get("limit", 10))

        # Get products with highest view counts
        queryset = self.get_queryset().order_by("-views_count")[:limit]

        serializer = ProductMetaStatsSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

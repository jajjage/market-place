# apps/products/product_meta/views.py

from rest_framework import permissions, status, filters
from rest_framework.decorators import action
from django.db.models import Prefetch
from django.core.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.views import BaseViewSet
from apps.products.product_image.models import ProductImage
from .models import ProductMeta
from .services import ProductMetaService as services
from .serializers import (
    ProductMetaDetailSerializer,
    ProductMetaWriteSerializer,
)


class ProductMetaViewSet(BaseViewSet):
    """
    API endpoint for managing and viewing product metadata.
    - Admin write operations for all metadata.
    - Read operations are public.
    - Owner operations for managing their own product metadata.
    - Specialized actions for retrieving popular/featured meta.
    """

    # Base queryset with performance optimizations
    queryset = (
        ProductMeta.objects.select_related("product")
        .prefetch_related(
            Prefetch(
                "product__images",
                queryset=ProductImage.objects.order_by("-is_primary"),
                to_attr="prefetched_images_list",
            )
        )
        .all()
    )
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["views_count", "created_at"]
    ordering = ["-views_count"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in [
            "create",
            "update",
            "partial_update",
            "update_my_product_meta",
        ]:
            return ProductMetaWriteSerializer
        return ProductMetaDetailSerializer

    def get_permissions(self):
        """Custom permissions for different actions."""
        if self.action in [
            "list",
            "retrieve",
            "stats",
            "featured",
            "popular",
            "by_product",
        ]:
            # All read actions are public
            permission_classes = [permissions.AllowAny]
        elif self.action in ["my_products_meta", "update_my_product_meta"]:
            # Owner actions require authentication
            permission_classes = [permissions.IsAuthenticated]
        else:
            # Create, Update, Delete are for admins only
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    @extend_schema(
        summary="Get Statistics on Product Meta",
        parameters=[
            OpenApiParameter(
                name="min_views", description="Filter by minimum view count.", type=int
            ),
        ],
    )
    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Returns paginated metadata for products, with optional filtering."""
        queryset = self.get_queryset()
        min_views = request.query_params.get("min_views")
        if min_views:
            try:
                queryset = queryset.filter(views_count__gte=int(min_views))
            except (ValueError, TypeError):
                pass  # Ignore invalid param

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(data=serializer.data)

    @extend_schema(
        summary="Get Metadata for Featured Products",
        parameters=[
            OpenApiParameter(
                name="limit",
                description="Number of items to return.",
                type=int,
                default=10,
            )
        ],
    )
    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Returns a list of metadata for featured products."""
        try:
            limit = int(request.query_params.get("limit", 10))
        except (ValueError, TypeError):
            limit = 10

        queryset = services.get_featured_products_meta(limit=limit)
        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        return self.success_response(data=serializer.data)

    @extend_schema(
        summary="Get Metadata for Popular Products",
        parameters=[
            OpenApiParameter(
                name="limit",
                description="Number of items to return.",
                type=int,
                default=10,
            )
        ],
    )
    @action(detail=False, methods=["get"])
    def popular(self, request):
        """Returns a list of metadata for the most viewed products."""
        try:
            limit = int(request.query_params.get("limit", 10))
        except (ValueError, TypeError):
            limit = 10

        queryset = services.get_popular_products_meta(limit=limit)
        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        return self.success_response(data=serializer.data)

    @extend_schema(
        summary="Get Metadata by Product ID or Slug",
        parameters=[
            OpenApiParameter(
                name="product_id", description="ID of the product.", type=int
            ),
            OpenApiParameter(
                name="product_slug", description="Slug of the product.", type=str
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="by-product")
    def by_product(self, request):
        """
        Retrieves product metadata for a given product ID or slug.
        This endpoint reliably creates the meta object if it doesn't exist.
        """
        product_id = request.query_params.get("product_id")
        product_slug = request.query_params.get("product_slug")

        if not product_id and not product_slug:
            return self.error_response(
                message="Either product_id or product_slug parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            meta = services.get_product_meta_by_product(
                product_id=product_id, product_slug=product_slug
            )
            serializer = self.get_serializer(meta, context={"request": request})
            return self.success_response(data=serializer.data)
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Get Metadata for My Products",
        description="Returns metadata for all products owned by the authenticated user.",
        parameters=[
            OpenApiParameter(
                name="limit",
                description="Number of items to return.",
                type=int,
                default=None,
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="my-products")
    def my_products_meta(self, request):
        """
        Returns metadata for all products owned by the authenticated user.
        Creates metadata if it doesn't exist for any of their products.
        """
        limit = request.query_params.get("limit")
        if limit:
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                limit = None

        queryset = services.get_user_products_meta(request.user, limit=limit)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset, many=True, context={"request": request}
        )
        return self.success_response(data=serializer.data)

    @extend_schema(
        summary="Update Metadata for My Product",
        description="Update metadata for a product owned by the authenticated user.",
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="ID of the product to update metadata for.",
                type=int,
                required=True,
            ),
        ],
    )
    @action(detail=False, methods=["patch", "put"], url_path="update-my-product")
    def update_my_product_meta(self, request):
        """
        Update metadata for a product owned by the authenticated user.
        Creates metadata if it doesn't exist.
        """
        product_id = request.query_params.get("product_id")

        if not product_id:
            return self.error_response(
                message="product_id parameter is required.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id = int(product_id)
        except (ValueError, TypeError):
            return self.error_response(
                message="Invalid product_id format.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Validate the data first
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Update using the service
            meta = services.update_product_meta(
                product_id=product_id, user=request.user, data=serializer.validated_data
            )

            # Return updated data
            response_serializer = ProductMetaDetailSerializer(
                meta, context={"request": request}
            )
            return self.success_response(data=response_serializer.data)

        except PermissionDenied as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    # Remove the increment_view action since this should be handled at product level
    # @action(detail=True, methods=["post"])
    # def increment_view(self, request, pk=None):
    #     """REMOVED: View counting should happen at the Product level, not here."""
    #     pass

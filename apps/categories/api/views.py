from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema

from apps.core.views import BaseViewSet

from ..throttle import CategoryRateThrottle


from ..models import Category
from ..services import CACHE_TTL, CategoryService
from .serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryWriteSerializer,
    CategoryBreadcrumbSerializer,
    CategoryTreeSerializer,
)
from .schema import category_viewset_schema


@extend_schema(tags=["Categories"])
class CategoryViewSet(BaseViewSet):
    """
    API endpoint for managing product categories.
    Supports hierarchical category structures with parent-child relationships.
    """

    queryset = Category.objects.select_related("parent").filter(is_active=True)
    # permission_classes = []
    throttle_classes = [CategoryRateThrottle]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_map = {
            "list": CategoryListSerializer,
            "create": CategoryWriteSerializer,
            "update": CategoryWriteSerializer,
            "partial_update": CategoryWriteSerializer,
            "breadcrumb": CategoryBreadcrumbSerializer,
            "tree": CategoryTreeSerializer,
        }
        return serializer_map.get(self.action, CategoryDetailSerializer)

    def get_queryset(self):
        """Optimize queryset based on action."""
        queryset = super().get_queryset()

        if self.action == "list":
            return queryset.prefetch_related("subcategories")
        elif self.action in ["retrieve", "breadcrumb"]:
            return queryset.select_related("parent")

        return queryset

    def perform_create(self, serializer):
        """Create a new category using service layer."""

        category = CategoryService.create_category(
            serializer.validated_data, user=self.request.user
        )
        serializer.instance = category

    @extend_schema(**category_viewset_schema.get("tree", {}))
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get hierarchical tree of categories."""
        max_depth = min(int(request.query_params.get("depth", 3)), 5)  # Limit depth
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )

        tree_data = CategoryService.get_category_tree(max_depth, include_inactive)
        return Response(tree_data)

    @extend_schema(**category_viewset_schema.get("subcategories", {}))
    @action(detail=True, methods=["get"])
    def subcategories(self, request, pk=None):
        """Get direct subcategories of a specific category."""
        category = self.get_object()
        subcategories = category.subcategories.filter(is_active=True).select_related(
            "parent"
        )

        serializer = CategoryListSerializer(
            subcategories, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(**category_viewset_schema.get("breadcrumb", {}))
    @action(detail=True, methods=["get"])
    def breadcrumb(self, request, pk=None):
        """Get breadcrumb path for a category."""
        breadcrumb_path = CategoryService.get_breadcrumb_path(int(pk))
        return Response({"path": breadcrumb_path})

    @extend_schema(**category_viewset_schema.get("products", {}))
    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get products belonging to this category."""
        from apps.products.product_base.serializers import ProductListSerializer

        # Parse filters
        filters = {}
        for param in ["price_min", "price_max", "brand", "in_stock"]:
            if param in request.query_params:
                filters[param] = request.query_params[param]

        include_subcategories = (
            request.query_params.get("include_subcategories", "false").lower() == "true"
        )

        result = CategoryService.get_category_with_products(
            int(pk), include_subcategories, filters
        )

        if not result:
            return Response(
                {"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND
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

    @extend_schema(**category_viewset_schema.get("popular", {}))
    @method_decorator(cache_page(CACHE_TTL))  # Cache for 30 minutes
    @action(detail=False, methods=["get"])
    def popular(self, request):
        """Get most popular categories based on product count."""
        limit = min(int(request.query_params.get("limit", 10)), 50)  # Limit to 50

        categories = CategoryService.get_popular_categories(limit)
        serializer = CategoryListSerializer(
            categories, many=True, context={"request": request}
        )
        return Response(serializer.data)


class CategoryAdminViewSet(BaseViewSet):
    """
    Admin-only endpoint for managing categories, including inactive ones.
    """

    queryset = Category.objects.all()
    # permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return CategoryWriteSerializer
        return CategoryDetailSerializer

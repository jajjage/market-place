from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.categories.throttle import CategoryRateThrottle
from apps.core.throttle import ThrottledException
from apps.core.views import BaseViewSet
from apps.core.permissions import IsOwnerOrReadOnly
from apps.categories.models import Category
from apps.categories.services import CACHE_TTL, CategoryService
from apps.categories.serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryWriteSerializer,
    CategoryBreadcrumbSerializer,
    CategoryTreeSerializer,
)


class CategoryViewSet(BaseViewSet):
    """
    API endpoint for managing product categories.
    Supports hierarchical category structures with parent-child relationships.
    """

    queryset = Category.objects.select_related("parent").filter(is_active=True)
    permission_classes = [IsOwnerOrReadOnly]
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

    def create(self, request, *args, **kwargs):
        """Create a new category using service layer."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            category = CategoryService.create_category(
                serializer.validated_data, user=request.user
            )

            response_serializer = CategoryDetailSerializer(
                category, context={"request": request}
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        parameters=[
            OpenApiParameter(name="depth", description="Maximum depth", type=int),
            OpenApiParameter(
                name="include_inactive",
                description="Include inactive categories",
                type=bool,
            ),
        ]
    )
    @method_decorator(cache_page(CACHE_TTL))  # Cache for 15 minutes
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get hierarchical tree of categories."""
        max_depth = min(int(request.query_params.get("depth", 3)), 5)  # Limit depth
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )

        tree_data = CategoryService.get_category_tree(max_depth, include_inactive)
        return Response(tree_data)

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

    @action(detail=True, methods=["get"])
    def breadcrumb(self, request, pk=None):
        """Get breadcrumb path for a category."""
        breadcrumb_path = CategoryService.get_breadcrumb_path(int(pk))
        return Response({"path": breadcrumb_path})

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="include_subcategories",
                description="Include products from subcategories",
                type=bool,
            ),
            OpenApiParameter(
                name="price_min", description="Minimum price filter", type=float
            ),
            OpenApiParameter(
                name="price_max", description="Maximum price filter", type=float
            ),
            OpenApiParameter(name="brand", description="Brand slug filter", type=str),
            OpenApiParameter(
                name="in_stock", description="Only in-stock products", type=bool
            ),
        ]
    )
    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get products belonging to this category."""
        from apps.products.serializers import ProductListSerializer

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

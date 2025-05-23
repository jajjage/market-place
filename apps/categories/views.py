from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.permissions import ReadWriteUserTypePermission
from apps.core.views import BaseViewSet
from .models import Category
from .serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryWriteSerializer,
    CategoryBreadcrumbSerializer,
)


class CategoryViewSet(BaseViewSet):
    """
    API endpoint for managing product categories.
    Supports hierarchical category structures with parent-child relationships.
    """

    queryset = Category.objects.all()
    permission_read_user_types = ["BUYER", "SELLER"]
    permission_write_user_types = ["SELLER"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return CategoryListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return CategoryWriteSerializer
        elif self.action == "breadcrumb":
            return CategoryBreadcrumbSerializer
        return CategoryDetailSerializer

    def get_permissions(self):
        """
        Custom permissions:
        - List/retrieve: Anyone can view categories
        - Create/update/delete: Only staff/admin users
        """
        if self.action in ["list", "retrieve", "breadcrumb", "subcategories", "tree"]:
            permission_classes = [ReadWriteUserTypePermission]
        else:
            permission_classes = [ReadWriteUserTypePermission]
        return [permission() for permission in permission_classes]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="depth",
                description="Maximum depth of category tree",
                required=False,
                type=int,
            )
        ]
    )
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """
        Get hierarchical tree of categories.
        Optional query param 'depth' controls max depth.
        """
        # Get top-level categories (no parent)
        root_categories = Category.objects.filter(parent=None)

        # Get optional depth parameter
        try:
            max_depth = int(request.query_params.get("depth", 3))
        except ValueError:
            max_depth = 3

        def build_tree(categories, current_depth=0):
            if current_depth >= max_depth:
                return []

            result = []
            for category in categories:
                category_data = CategoryListSerializer(
                    category, context={"request": request}
                ).data
                children = category.subcategories.all()

                if children:
                    category_data["subcategories"] = build_tree(
                        children, current_depth + 1
                    )
                else:
                    category_data["subcategories"] = []

                result.append(category_data)
            return result

        tree_data = build_tree(root_categories)
        return Response(tree_data)

    @action(detail=True, methods=["get"])
    def subcategories(self, request, pk=None):
        """
        Get direct subcategories of a specific category.
        """
        category = self.get_object()
        subcategories = category.subcategories.all()
        serializer = CategoryListSerializer(
            subcategories, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def breadcrumb(self, request, pk=None):
        """
        Get breadcrumb path for a category.
        Returns path from root category to this category.
        """
        category = self.get_object()
        serializer = CategoryBreadcrumbSerializer(
            category, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """
        Get products belonging to this category.
        """
        from apps.products.serializers import ProductListSerializer
        from apps.products.models import Product

        category = self.get_object()

        # Get optional query parameters
        include_subcategories = (
            request.query_params.get("include_subcategories", "false").lower() == "true"
        )

        if include_subcategories:
            # Get all subcategories recursively
            def get_subcategory_ids(category_id):
                subcategory_ids = []
                subcategories = Category.objects.filter(parent_id=category_id)

                for subcategory in subcategories:
                    subcategory_ids.append(subcategory.id)
                    subcategory_ids.extend(get_subcategory_ids(subcategory.id))

                return subcategory_ids

            category_ids = [category.id] + get_subcategory_ids(category.id)
            products = Product.objects.filter(
                category_id__in=category_ids, is_active=True
            )
        else:
            # Just get products directly in this category
            products = Product.objects.filter(category=category, is_active=True)

        # Apply pagination
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

    @action(detail=False, methods=["get"])
    def popular(self, request):
        """
        Get most popular categories based on product count.
        """
        limit = int(request.query_params.get("limit", 10))

        # Get categories with product counts
        categories = (
            Category.objects.annotate(product_count=Count("product"))
            .filter(is_active=True, product_count__gt=0)
            .order_by("-product_count")[:limit]
        )

        serializer = CategoryListSerializer(
            categories, many=True, context={"request": request}
        )
        return Response(serializer.data)

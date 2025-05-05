from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count


from apps.core.permissions import ReadWriteUserTypePermission
from apps.core.views import BaseViewSet
from apps.products.models import ProductCondition
from apps.products.serializers import (
    ProductConditionListSerializer,
    ProductConditionDetailSerializer,
    ProductConditionWriteSerializer,
)


class ProductConditionViewSet(BaseViewSet):
    """
    API endpoint for managing product conditions.
    Provides CRUD operations for product condition types.
    """

    queryset = ProductCondition.objects.all()
    permission_read_user_types = ["BUYER", "SELLER"]
    permission_write_user_types = ["SELLER"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_serializer_class(self):
        print(self.action)
        """Return appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return ProductConditionWriteSerializer
        elif self.action == "list":
            return ProductConditionListSerializer
        return ProductConditionDetailSerializer

    def get_permissions(self):
        """
        Custom permissions:
        - List/retrieve: Anyone can view product conditions
        - Create/update/delete: Only staff/admin users
        """
        if self.action in ["list", "retrieve"]:
            permission_classes = [ReadWriteUserTypePermission]
        else:
            permission_classes = [ReadWriteUserTypePermission]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def products(self, request, pk=None):
        """
        Get products using this condition.
        """
        from apps.products.serializers import ProductListSerializer
        from apps.products.models import Product

        condition = self.get_object()
        products = Product.objects.filter(condition=condition, is_active=True)

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
        Get most popular product conditions based on usage count.
        """
        limit = int(request.query_params.get("limit", 10))

        # Get conditions with product counts
        conditions = (
            ProductCondition.objects.annotate(product_count=Count("product"))
            .filter(is_active=True, product_count__gt=0)
            .order_by("-product_count")[:limit]
        )

        serializer = ProductConditionListSerializer(
            conditions, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """
        Get only active product conditions.
        """
        conditions = ProductCondition.objects.filter(is_active=True)
        serializer = ProductConditionListSerializer(
            conditions, many=True, context={"request": request}
        )
        return Response(serializer.data)

# views.py
from rest_framework import viewsets, permissions, generics
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from apps.products.utils.product_filters import ProductFilter
from .models import Product, Category
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductBaseSerializer,
)
from .permissions import IsSellerAndOwnerOrReadOnly
from drf_spectacular.utils import extend_schema
from .schema import PRODUCT_DETAIL_RESPONSE_SCHEMA, PRODUCT_LIST_RESPONSE_SCHEMA


class CategoryViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class ProductViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """

    queryset = Product.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["title", "description", "specifications"]
    ordering_fields = ["price", "created_at", "updated_at", "views_count"]
    ordering = ["-created_at"]  # Default ordering

    permission_classes = [IsSellerAndOwnerOrReadOnly]

    def get_serializer_class(self):
        """
        Use different serializers for list and detail views.
        """
        print(f"Current action: {self.action}")
        if self.action in ["list", "retrieve", "update", "partial_update"]:
            return ProductDetailSerializer
        return ProductBaseSerializer

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @extend_schema(
        responses=PRODUCT_LIST_RESPONSE_SCHEMA, description="List all products."
    )
    def list(self, request, *args, **kwargs):
        """List all products."""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        responses=PRODUCT_DETAIL_RESPONSE_SCHEMA,
        description="Retrieve a product by ID.",
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a product by ID."""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        request=ProductBaseSerializer,
        responses=PRODUCT_DETAIL_RESPONSE_SCHEMA,
        description="Create a new product.",
    )
    def create(self, request, *args, **kwargs):
        """Create a new product."""
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=ProductBaseSerializer,
        responses=PRODUCT_DETAIL_RESPONSE_SCHEMA,
        description="Update a product.",
    )
    def update(self, request, *args, **kwargs):
        """Update a product."""
        return super().update(request, *args, **kwargs)


# View to retrieve products by UUID
@extend_schema(
    responses=PRODUCT_DETAIL_RESPONSE_SCHEMA,
)
class ProductDetailByUUID(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    lookup_field = "uuid"
    # We allow anyone to view a product via its UUID
    permission_classes = [permissions.AllowAny]


# View to retrieve products by short code - this is what makes the sharing easy!
@extend_schema(
    responses=PRODUCT_DETAIL_RESPONSE_SCHEMA,
)
class ProductDetailByShortCode(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    lookup_field = "short_code"
    # We allow anyone to view a product via its short code
    permission_classes = [permissions.AllowAny]

import logging
from django.utils.decorators import method_decorator
from rest_framework import status
from django.views.decorators.vary import vary_on_cookie
from rest_framework import permissions, filters, generics
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.views import BaseAPIView, BaseViewSet
from apps.products.product_base.services import (
    ProductMyService,
    ProductFeaturedService,
    ProductStatsService,
    ProductDetailService,
    ProductListService,
    ProductToggleService,
    ProductShareService,
    ProductWatchersService,
    ProductConditionService,
)
from apps.products.product_base.utils.seller import is_product_owner
from apps.products.product_metadata.services import ProductMetaService as meta_services
from apps.products.product_metadata.serializers import (
    ProductMetaDetailSerializer,
    ProductMetaWriteSerializer,
)
from apps.products.product_metadata.services import ProductMetaService
from .models import (
    Product,
)
from .serializers import (
    ProductCreateSerializer,
    ProductUpdateSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductStatsSerializer,
)
from .utils.product_filters import ProductFilter
from apps.products.product_base.utils.rate_limiting import (
    ProductListRateThrottle,
    ProductStatsRateThrottle,
    ProductFeaturedRateThrottle,
)

from drf_spectacular.utils import extend_schema

logger = logging.getLogger("products_performance")


class ProductViewSet(BaseViewSet):
    """
    ViewSet for managing products with different serializers for different operations.
    Supports CRUD operations, filtering, searching, and statistics.
    """

    logger = logging.getLogger("products_performance")

    CACHE_TTL = 60 * 15  # 15 minutes cache
    STATS_CACHE_TTL = 60 * 30  # 30 minutes cache for stats

    queryset = Product.objects.all()
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilter
    search_fields = ["title", "description", "slug", "short_code"]
    ordering_fields = ["price", "created_at", "title", "inventory_count"]
    ordering = ["-created_at"]
    throttle_classes = [ProductListRateThrottle]

    def get_permissions(self):
        """Custom permissions for different actions."""
        if self.action in ["list"]:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_context(self):
        """
        Ensures the request context is passed to the serializer.
        This is often implicitly done by ModelViewSet, but explicitly defining it
        is good practice or necessary for custom ViewSets.
        """
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        """
        Get optimized and cached queryset.
        """
        # Start with the base queryset (this should always be a QuerySet)
        base_queryset = super().get_queryset()

        # Apply permission-based filtering FIRST (while it's still a QuerySet)
        if self.action == "list" and not self.request.user.is_staff:
            base_queryset = base_queryset.filter(is_active=True)
        elif self.action in ["retrieve", "update", "partial_update", "destroy"]:
            if not self.request.user.is_staff:
                base_queryset = base_queryset.filter(seller=self.request.user)
        # request = self.request
        # Then apply caching and optimization (ensure this returns a QuerySet)
        optimized_queryset = ProductListService.get_cached_product_list(
            self, base_queryset
        )

        # Ensure we're returning a QuerySet
        if not hasattr(optimized_queryset, "filter"):
            # If somehow we got a list, convert back to QuerySet
            if isinstance(optimized_queryset, (list, tuple)) and optimized_queryset:
                product_ids = [item.id for item in optimized_queryset]
                return base_queryset.filter(id__in=product_ids)
            else:
                return base_queryset

        return optimized_queryset

    def get_serializer_class(self):
        """
        Return different serializers based on the action.
        - create: Minimal serializer requiring only title
        - update/partial_update: Serializer for updating product details
        - list: Optimized serializer for listing products
        - retrieve: Detailed serializer with all information
        - stats: Specialized serializer for statistics
        """
        if self.action == "create":
            return ProductCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ProductUpdateSerializer
        elif self.action == "list":
            return ProductListSerializer
        elif self.action == "stats":
            return ProductStatsSerializer
        return ProductDetailSerializer

    @method_decorator(vary_on_cookie)
    @action(
        detail=False,
        url_path="my-products",
        methods=["get"],
        throttle_classes=[ProductListRateThrottle],
    )
    def my_products(self, request):
        return ProductMyService.get_my_products(self, request)

    @method_decorator(vary_on_cookie)
    @action(
        detail=False, methods=["get"], throttle_classes=[ProductFeaturedRateThrottle]
    )
    def featured(self, request):
        return ProductFeaturedService.get_featured(self, request)

    @method_decorator(vary_on_cookie)
    @action(detail=False, methods=["get"], throttle_classes=[ProductStatsRateThrottle])
    def stats(self, request):
        return ProductStatsService.get_stats_view(self, request)

    @action(detail=True, url_path="toggle-active", methods=["post"])
    def toggle_active(self, request, pk=None):
        if not is_product_owner(self, request):
            return self.error_response(
                message="You can't update items that doesn't belong to you",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return ProductToggleService.toggle_active(self, request, pk)

    @action(detail=True, url_path="toggle-featured", methods=["post"])
    def toggle_featured(self, request, pk=None):
        if not is_product_owner(self, request):
            return self.error_response(
                message="You can't update items that doesn't belong to you",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return ProductToggleService.toggle_featured(self, request, pk)

    @action(detail=True, url_path="toggle-negotiation", methods=["post"])
    def toggle_negotiation(self, request, pk=None):
        if not is_product_owner(self, request):
            return self.error_response(
                message="You can't update items that doesn't belong to you",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return ProductToggleService.toggle_negotiation(self, request, pk)

    @action(detail=True, methods=["get"])
    def watchers(self, request, pk=None):
        return ProductWatchersService.get_watchers(self, request, pk)

    @action(
        detail=False, url_path=r"share-links/(?P<short_code>[^/.]+)", methods=["get"]
    )
    def get_share_links(self, request, short_code=None):
        return ProductShareService.get_share_links(self, request, short_code)

    @action(
        detail=False, methods=["get"], url_path="by-condition/(?P<condition_id>[^/.]+)"
    )
    def by_condition(self, request, condition_id=None):
        return ProductConditionService.by_condition(self, request, condition_id)

    @extend_schema(
        summary="Manage Product Metadata",
        description="Get or update metadata for a product owned by the authenticated user.",
        responses={
            200: ProductMetaDetailSerializer,
            403: "Not the owner of this product",
            404: "Product not found",
        },
    )
    @action(detail=True, methods=["get", "patch", "put"])
    def manage_metadata(self, request, pk=None):
        """
        Allow product owners to manage their product's metadata.
        GET: Retrieve current metadata (creates if doesn't exist)
        PATCH/PUT: Update metadata
        """
        instance = self.get_object()

        # Check ownership (assuming your Product model has an 'owner' field)
        if hasattr(instance, "owner") and instance.owner != request.user:
            return self.error_response(
                message="You can only manage metadata for your own products",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "GET":
            # Get or create metadata
            try:
                meta, created = meta_services.get_or_create_product_meta(
                    product_id=instance.id, user=request.user, data=self.request.data
                )
                serializer = ProductMetaDetailSerializer(
                    meta, context={"request": request}
                )
                return self.success_response(data=serializer.data)
            except Exception as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )

        else:  # PATCH or PUT
            # Update metadata
            try:
                # You might want to create a separate serializer for metadata updates
                # For now, assuming you have the data in request.data
                meta, create = meta_services.get_or_create_product_meta(
                    product_id=instance.id, user=request.user, data=request.data
                )
                serializer = ProductMetaWriteSerializer(
                    meta, context={"request": request}
                )
                return self.success_response(data=serializer.data)
            except Exception as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )


# Product retrieval by short code for social media sharing
class ProductDetailByShortCode(generics.RetrieveAPIView, BaseAPIView):
    """
    Retrieve a product by its short code.
    Used for both viewing and sharing via short URLs.
    """

    logger = logging.getLogger("products_performance")
    CACHE_TTL = 60 * 15  # 15 minutes cache
    STATS_CACHE_TTL = 60 * 30  # 30 minutes cache for stats

    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    lookup_field = "short_code"
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        product = ProductDetailService.retrieve_by_shortcode(
            self, request, *args, **kwargs
        )

        if product:
            instance = self.get_object()
            try:
                ProductMetaService.increment_product_view_count(
                    product_id=instance.id, use_cache_buffer=True
                )
            except Exception as e:
                print(instance.id)
                print(e)
                pass
        return product

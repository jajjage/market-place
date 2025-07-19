import logging
from django.utils.decorators import method_decorator
from rest_framework import status
from django.views.decorators.vary import vary_on_cookie
from rest_framework import permissions, filters, generics
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.views import BaseAPIView, BaseViewSet

# from apps.products.product_base.schema import PRODUCT_MANAGE_METADATA
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
from apps.products.product_base.tasks import generate_seo_description_for_product
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


logger = logging.getLogger(__name__)


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

    def get_queryset(self):
        """
        CLEAN VERSION: Only handle QuerySet logic, no caching.
        Always returns a proper QuerySet for DRF to work with.
        """
        # Start with the base queryset
        base_queryset = super().get_queryset()

        # Apply permission-based filtering
        if self.action == "list" and not self.request.user.is_staff:
            base_queryset = base_queryset.filter(is_active=True)
        elif self.action in ["retrieve", "update", "partial_update", "destroy"]:
            if not self.request.user.is_staff:
                base_queryset = base_queryset.filter(seller=self.request.user)

        # For list action, return optimized queryset
        if self.action == "list":
            return ProductListService.get_optimized_product_queryset(base_queryset)

        # For other actions, use your existing service
        return base_queryset

    def list(self, request, *args, **kwargs):
        """
        Handle caching ONLY in the list method using version-based caching.
        This is cleaner and doesn't interfere with DRF's QuerySet expectations.
        """
        # Try cache first using the new version-based approach
        cached_data = ProductListService.get_cached_list(request)
        if cached_data:
            logger.info("Cache HIT for product list")

            # Handle pagination for cached data
            page = self.paginate_queryset(cached_data)
            if page is not None:
                return self.get_paginated_response(page)

            return self.success_response(data=cached_data)

        # Cache miss - proceed with normal DRF flow
        logger.info("Cache MISS for product list")

        # Get the optimized queryset (this will use get_queryset())
        queryset = self.filter_queryset(self.get_queryset())

        # Handle pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            serialized_data = serializer.data

            # Cache the serialized data using version-based caching
            try:
                ProductListService.set_cached_list(request, serialized_data)
                logger.info(
                    f"Cached serialized product data: {len(serialized_data)} items"
                )
            except Exception as e:
                logger.warning(f"Failed to cache product list: {str(e)}")

            return self.get_paginated_response(serialized_data)

        # Non-paginated response
        serializer = self.get_serializer(queryset, many=True)
        serialized_data = serializer.data

        # Cache the serialized data using version-based caching
        try:
            ProductListService.set_cached_list(request, serialized_data)
            logger.info(f"Cached serialized product data: {len(serialized_data)} items")
        except Exception as e:
            logger.warning(f"Failed to cache product list: {str(e)}")

        return self.success_response(data=serialized_data)

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

    @action(detail=True, methods=["get", "put", "patch"], url_path="manage_metadata")
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

    @action(
        detail=True,
        methods=["post"],
        url_path="generate-seo-description",
        throttle_classes=[ProductListRateThrottle],
    )
    def generate_seo_description(self, request, pk=None):
        """
        Generate an SEO description for a product.
        This is a POST action that triggers the background task to generate the description.
        """
        instance = self.get_object()

        if not is_product_owner(self, request):
            return self.error_response(
                message="You can't generate SEO descriptions for products that don't belong to you",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Trigger the background task
        result = generate_seo_description_for_product.delay(instance.id)

        if result.successful:
            return self.success_response(
                data={
                    "message": "SEO description generation started",
                    "task_id": result.task_id,
                }
            )
        else:
            return self.error_response(
                message=result.error, status_code=status.HTTP_400_BAD_REQUEST
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
                logger.error(
                    f"Error incrementing view count for product {instance.id}: {e}"
                )
        return product

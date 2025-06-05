import logging
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework import permissions, filters, generics
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from apps.core.permissions import IsOwnerOrReadOnly
from apps.core.views import BaseAPIView, BaseViewSet
from apps.products.product_condition.services import ProductConditionService
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
from apps.core.utils.cache_manager import CacheManager
from apps.products.product_base.utils.rate_limiting import (
    ProductListRateThrottle,
    ProductStatsRateThrottle,
    ProductFeaturedRateThrottle,
)
from apps.products.product_base.services.product_stats_service import (
    ProductStatsService,
)
from apps.products.product_base.services.product_featured_service import (
    ProductFeaturedService,
)
from apps.products.product_base.services.product_my_service import ProductMyService
from apps.products.product_base.services.product_share_service import (
    ProductShareService,
)
from apps.products.product_base.services.product_watchers_service import (
    ProductWatchersService,
)

from apps.products.product_base.services.product_toggle_service import (
    ProductToggleService,
)
from apps.products.product_base.services.product_detail_service import (
    ProductDetailService,
)


class ProductViewSet(BaseViewSet):
    """
    ViewSet for managing products with different serializers for different operations.
    Supports CRUD operations, filtering, searching, and statistics.
    """

    logger = logging.getLogger("products_performance")
    CACHE_TTL = 60 * 15  # 15 minutes cache
    STATS_CACHE_TTL = 60 * 30  # 30 minutes cache for stats

    queryset = Product.objects.all()
    permission_classes = [IsOwnerOrReadOnly]
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
        queryset = super().get_queryset()

        # Optimize queries for related fields
        queryset = queryset.select_related(
            "brand", "category", "condition", "seller"
        ).prefetch_related("images", "variants", "watchers", "breadcrumbs")

        # For list action, show only active products to non-staff
        if self.action == "list" and not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)

        # For detail, update, delete: only owner or staff can access
        elif self.action in ["retrieve", "update", "partial_update", "destroy"]:
            if not self.request.user.is_staff:
                queryset = queryset.filter(seller=self.request.user)

        # For other actions like create or custom actions, the base queryset is used

        return queryset

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

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    @action(
        detail=False,
        url_path="my-products",
        methods=["get"],
        throttle_classes=[ProductListRateThrottle],
    )
    def my_products(self, request):
        return ProductMyService.get_my_products(self, request)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    @action(
        detail=False, methods=["get"], throttle_classes=[ProductFeaturedRateThrottle]
    )
    def featured(self, request):
        return ProductFeaturedService.get_featured(self, request)

    @method_decorator(cache_page(STATS_CACHE_TTL))
    @method_decorator(vary_on_cookie)
    @action(detail=False, methods=["get"], throttle_classes=[ProductStatsRateThrottle])
    def stats(self, request):
        return ProductStatsService.get_stats_view(self, request)

    def perform_update(self, serializer):
        instance = serializer.instance
        CacheManager.invalidate("product_base", id=instance.pk)
        serializer.save()

    def perform_create(self, serializer):
        instance = serializer.instance
        CacheManager.invalidate("product_base", id=instance.pk)
        serializer.save()

    def perform_destroy(self, instance):
        CacheManager.invalidate("product", id=instance.pk)
        instance.delete()

    @action(detail=True, url_path="toggle-active", methods=["post"])
    def toggle_active(self, request, pk=None):
        return ProductToggleService.toggle_active(self, request, pk)

    @action(detail=True, url_path="toggle-featured", methods=["post"])
    def toggle_featured(self, request, pk=None):
        return ProductToggleService.toggle_featured(self, request, pk)

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


# Product retrieval by short code for social media sharing
class ProductDetailByShortCode(generics.RetrieveAPIView, BaseAPIView):
    """
    Retrieve a product by its short code.
    Used for both viewing and sharing via short URLs.
    """

    logger = logging.getLogger(__name__)
    CACHE_TTL = 60 * 15  # 15 minutes cache
    STATS_CACHE_TTL = 60 * 30  # 30 minutes cache for stats

    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    lookup_field = "short_code"
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def retrieve(self, request, *args, **kwargs):
        return ProductDetailService.retrieve_by_shortcode(
            self, request, *args, **kwargs
        )

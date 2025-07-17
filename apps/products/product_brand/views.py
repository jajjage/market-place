from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.views import BaseViewSet
from apps.products.product_brand.documents import BrandDocument
from apps.products.product_brand.utils.rate_limiting import (
    BrandCreateThrottle,
    BrandSearchThrottle,
)
from .models import Brand, BrandRequest, BrandVariant
from .serializers import (
    BrandListSerializer,
    BrandDetailSerializer,
    BrandCreateSerializer,
    BrandRequestSerializer,
    BrandSearchSerializer,
    BrandVariantSerializer,
)
from .services import BrandService, BrandRequestService, BrandVariantService
from .utils.filters import BrandFilter


class BrandViewSet(BaseViewSet):
    """
    Brand ViewSet with optimized queries and caching

    Endpoints:
    - GET /brands/ - List brands with filtering and search
    - GET /brands/{id}/ - Brand detail
    - POST /brands/ - Create brand (admin only)
    - PUT/PATCH /brands/{id}/ - Update brand (admin only)
    - DELETE /brands/{id}/ - Delete brand (admin only)
    - GET /brands/featured/ - Featured brands
    - GET /brands/search/ - Advanced search
    - GET /brands/{id}/analytics/ - Brand analytics (admin only)
    """

    cache_list_seconds = 300  # List is cached for 5 minutes
    cache_retrieve_seconds = 600
    queryset = Brand.objects.all()
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = BrandFilter
    search_fields = ["name", "description", "country_of_origin"]
    ordering_fields = [
        "name",
        "founded_year",
        "cached_product_count",
        "cached_average_rating",
    ]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action in ("list", "search"):
            return BrandListSerializer
        elif self.action == "create":
            return BrandCreateSerializer
        else:
            return BrandDetailSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "analytics",
        ]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_throttles(self):
        if self.action == "search":
            throttle_classes = [BrandSearchThrottle]
        else:
            throttle_classes = [BrandCreateThrottle]
        return [throttle() for throttle in throttle_classes]

    def get_queryset(self):
        """Optimize queryset based on action"""
        queryset = Brand.objects.active()

        if self.action == "list":
            # For list view, use lightweight queryset with stats
            return queryset.with_stats().select_related()
        elif self.action == "retrieve":
            # For detail view, prefetch related data
            return queryset.prefetch_related("variants", "products")

        return queryset

    @action(detail=False, methods=["GET"])
    def featured(self, request):
        """Get featured brands"""
        limit = int(request.query_params.get("limit", 10))
        brands = BrandService.get_featured_brands(limit)
        serializer = BrandListSerializer(brands, many=True)
        return self.success_response(
            data=serializer.data, status_code=status.HTTP_200_OK
        )

    @action(detail=True, methods=["GET"], permission_classes=[IsAdminUser])
    def analytics(self, request, pk=None):
        """Get brand analytics (admin only)"""
        brand = self.get_object()
        days = int(request.query_params.get("days", 30))

        analytics = BrandService.get_brand_analytics(brand.id, days)
        return self.success_response(data=analytics)

    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    def refresh_stats(self, request, pk=None):
        """Manually refresh brand statistics"""
        brand = self.get_object()
        from .tasks import update_brand_stats

        update_brand_stats.delay(brand.id)

        return self.success_response(message="Statistics refresh initiated")


class BrandRequestViewSet(BaseViewSet):
    """
    Brand Request ViewSet

    Endpoints:
    - GET /brand-requests/ - List requests (admin) or user's requests
    - POST /brand-requests/ - Submit new request
    - GET /brand-requests/{id}/ - Request detail
    - PATCH /brand-requests/{id}/process/ - Process request (admin only)
    """

    cache_list_seconds = 300  # List is cached for 5 minutes
    cache_retrieve_seconds = 600
    queryset = BrandRequest.objects.all()
    serializer_class = BrandRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter requests based on user role"""
        if self.request.user.is_staff:
            return BrandRequest.objects.all().select_related(
                "requested_by", "processed_by"
            )
        else:
            return BrandRequest.objects.filter(requested_by=self.request.user)

    def perform_create(self, serializer):
        """Create request with current user"""
        try:
            brand_request = BrandRequestService.submit_request(
                user=self.request.user,
                brand_name=serializer.validated_data["brand_name"],
                reason=serializer.validated_data["reason"],
                website=serializer.validated_data.get("website", ""),
            )
            serializer.instance = brand_request
        except ValueError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["PATCH"], permission_classes=[IsAdminUser])
    def process(self, request, pk=None):
        """Process a brand request (approve/reject)"""
        brand_request = self.get_object()
        action_type = request.data.get("action")  # 'approve' or 'reject'
        notes = request.data.get("notes", "")

        if action_type not in ["approve", "reject"]:
            return self.error_response(
                message='Action must be either "approve" or "reject"',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            processed_request = BrandRequestService.process_request(
                request_id=brand_request.id,
                admin_user=request.user,
                action=action_type,
                notes=notes,
            )

            serializer = self.get_serializer(processed_request)
            return self.success_response(
                data=serializer.data, status_code=status.HTTP_200_OK
            )

        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )


class BrandVariantViewSet(BaseViewSet):
    """Brand Variant management"""

    serializer_class = BrandVariantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        brand_id = self.kwargs.get("brand_pk")
        return BrandVariant.objects.filter(brand_id=brand_id, is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        brand_id = self.kwargs.get("brand_pk")
        variant = BrandVariantService.create_variant(
            brand_id=brand_id,
            variant_data=serializer.validated_data,
            created_by=(
                self.request.user if self.request.user.is_authenticated else None
            ),
        )
        serializer.instance = variant

    @action(detail=False, methods=["POST"], permission_classes=[IsAdminUser])
    def auto_generate(self, request, brand_pk=None):
        """Auto-generate variants for a brand"""
        variants = BrandVariantService.auto_generate_variants(brand_pk)
        serializer = BrandVariantSerializer(variants, many=True)
        return self.success_response(
            data={"variants": serializer.data, "created_count": len(variants)}
        )

    @action(detail=False, methods=["GET"])
    def for_locale(self, request, brand_pk=None):
        """Get variant for specific locale"""
        language_code = request.query_params.get("lang", "en")
        region_code = request.query_params.get("region", "")

        variant = BrandVariantService.get_variant_for_locale(
            brand_pk, language_code, region_code
        )

        if variant:
            serializer = BrandVariantSerializer(variant)
            return self.success_response(
                data=serializer.data, status_code=status.HTTP_200_OK
            )
        else:
            return self.error_response(
                message="No variant found for this locale",
                status_code=status.HTTP_404_NOT_FOUND,
            )


class BrandSearchView(APIView):
    """
    A simple search view for listing and finding brands.
    Supports full-text search, filtering by featured status, sorting, and pagination.
    """

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        page = int(request.query_params.get("page", 1))
        page_size = min(int(request.query_params.get("page_size", 50)), 200)
        sort_by = request.query_params.get("sort", "name")  # 'name' or 'product_count'

        # Start with the base search on the BrandDocument
        search = BrandDocument.search()

        # Apply text query if provided
        if query:
            search = search.query("match", name={"query": query, "fuzziness": "AUTO"})

        # Optional filter for featured brands
        if request.query_params.get("is_featured") == "true":
            search = search.filter("term", is_featured=True)

        # Apply sorting
        if sort_by == "product_count":
            search = search.sort({"cached_product_count": {"order": "desc"}})
        else:  # Default sort by name
            search = search.sort({"name.raw": {"order": "asc"}})

        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        search = search[start:end]

        # Execute the search
        response = search.execute()

        # Serialize the results
        serializer = BrandSearchSerializer(response.hits, many=True)

        total_hits = response.hits.total.value
        total_pages = (total_hits + page_size - 1) // page_size

        return Response(
            {
                "results": serializer.data,
                "total_count": total_hits,
                "page": page,
                "total_pages": total_pages,
            }
        )

from rest_framework import status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from apps.core.views import BaseViewSet
from apps.products.product_brand.documents import BrandDocument
from apps.products.product_brand.tasks import (
    auto_generate_brand_variants,
    bulk_generate_variants_for_template,
)
from apps.products.product_brand.utils.rate_limiting import (
    BrandCreateThrottle,
    BrandSearchThrottle,
)
from .models import Brand, BrandRequest, BrandVariant, BrandVariantTemplate
from .serializers import (
    BrandListSerializer,
    BrandDetailSerializer,
    BrandCreateSerializer,
    BrandRequestSerializer,
    BrandSearchSerializer,
    BrandVariantSerializer,
    BrandVariantTemplateSerializer,
)
from .services import (
    BrandService,
    BrandRequestService,
    BrandVariantService,
    BrandVariantTemplateService,
)
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
        return BrandVariant.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

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


class BrandVariantTemplateViewSet(BaseViewSet):
    """Enhanced Brand Variant Template management with auto-generation"""

    serializer_class = BrandVariantTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get all active templates"""
        return BrandVariantTemplate.objects.filter(is_active=True)

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    def generate_variants(self, request, pk=None):
        """Generate variants using this template"""
        template = self.get_object()
        brand_ids = request.data.get("brand_ids", [])
        force = request.data.get("force", False)

        if not brand_ids:
            # Generate for all eligible brands
            task_result = bulk_generate_variants_for_template.delay(template.id)
            return self.success_response(
                data={
                    "template_id": template.id,
                    "task_id": task_result.id,
                    "message": "Bulk generation task started",
                },
                status_code=status.HTTP_202_ACCEPTED,
            )
        else:
            # Generate for specific brands
            task_result = bulk_generate_variants_for_template.delay(
                template.id, brand_ids
            )
            return self.success_response(
                data={
                    "template_id": template.id,
                    "task_id": task_result.id,
                    "brand_ids": brand_ids,
                    "message": "Generation task started",
                },
                status_code=status.HTTP_202_ACCEPTED,
            )

    @action(detail=True, methods=["POST"], permission_classes=[IsAdminUser])
    def regenerate_variants(self, request, pk=None):
        """Regenerate all variants for this template"""
        template = self.get_object()
        force = request.data.get("force", False)

        result = BrandVariantTemplateService.regenerate_variants_from_template(
            template.id, force=force
        )

        if "error" in result:
            return self.error_response(
                message=result["error"], status_code=status.HTTP_400_BAD_REQUEST
            )

        return self.success_response(data=result, status_code=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=["POST"], permission_classes=[IsAdminUser])
    def manual_generate_for_brand(self, request):
        """Manually generate variants for a specific brand"""
        brand_id = request.data.get("brand_id")
        template_ids = request.data.get("template_ids", [])

        if not brand_id:
            return self.error_response(
                message="brand_id is required", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Use Celery task for async processing
        task_result = auto_generate_brand_variants.delay(brand_id)

        return self.success_response(
            data={
                "brand_id": brand_id,
                "task_id": task_result.id,
                "message": "Variant generation task started",
            },
            status_code=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["GET"])
    def generation_status(self, request):
        """Check the status of variant generation tasks"""
        task_id = request.query_params.get("task_id")

        if not task_id:
            return self.error_response(
                message="task_id is required", status_code=status.HTTP_400_BAD_REQUEST
            )

        # Check Celery task status
        from celery.result import AsyncResult

        task_result = AsyncResult(task_id)

        response_data = {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result if task_result.ready() else None,
        }

        return self.success_response(data=response_data, status_code=status.HTTP_200_OK)


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

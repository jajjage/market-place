from rest_framework import status, permissions
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from apps.core.utils.cache_manager import CacheKeyManager
from apps.core.views import BaseViewSet
from apps.disputes.models import Dispute
from apps.disputes.utils.rate_limiting import DisputeRateThrottle
from .serializers import (
    DisputeCreateSerializer,
    DisputeDetailSerializer,
    DisputeResolutionSerializer,
    DisputeListSerializer,
)
from .services import DisputeService
from .permissions import DisputePermission
from apps.disputes.utils.filters import DisputeFilter
import logging
from rest_framework.exceptions import ValidationError

logger = logging.getLogger("dispute_performance")


class DisputeViewSet(BaseViewSet):
    """
    ViewSet for managing disputes
    - Create: POST /disputes/
    - List: GET /disputes/
    - Detail: GET /disputes/{id}/
    - Resolve: POST /disputes/{id}/resolve/ (admin only)
    - My Disputes: GET /disputes/my/
    """

    queryset = Dispute.objects.all()
    permission_classes = [permissions.IsAuthenticated, DisputePermission]
    filter_backends = [DjangoFilterBackend]
    filterset_class = DisputeFilter

    def get_serializer_class(self):
        if self.action == "create":
            return DisputeCreateSerializer
        elif self.action == "resolve":
            return DisputeResolutionSerializer
        elif self.action == "list" or self.action == "my_disputes":
            return DisputeListSerializer
        return DisputeDetailSerializer

    def get_throttles(self):
        """Apply rate limiting to create action"""
        if self.action == "create":
            return [DisputeRateThrottle()]
        return []

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        if user.is_staff:
            return Dispute.objects.all().select_related(
                "opened_by", "resolved_by", "transaction"
            )
        else:
            # Users can only see their own disputes
            return Dispute.objects.filter(
                Q(transaction__buyer=user) | Q(transaction__seller=user)
            ).select_related("opened_by", "resolved_by", "transaction")

    def create(self, request, *args, **kwargs):
        """Create a new dispute"""
        start_time = timezone.now()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            dispute = DisputeService.create_dispute(
                transaction_id=serializer.validated_data["transaction_id"],
                user=request.user,
                reason=serializer.validated_data["reason"],
                description=serializer.validated_data["description"],
            )

            response_serializer = DisputeDetailSerializer(dispute)

            duration = (timezone.now() - start_time).total_seconds() * 1000
            logger.info(f"Created dispute via API in {duration:.2f}ms")

            return self.success_response(
                data=response_serializer.data, status_code=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    def retrieve(self, request, *args, **kwargs):
        """Get dispute details with caching"""
        dispute_id = kwargs.get("pk")
        cache_key = CacheKeyManager.make_key("dispute", "detail", id=dispute_id)

        # Try cache first
        from django.core.cache import cache

        cached_dispute = cache.get(cache_key)
        if cached_dispute is not None:
            logger.info(f"Retrieved dispute {dispute_id} from cache")
            return self.success_response(data=cached_dispute)

        start_time = timezone.now()

        dispute = self.get_object()
        serializer = self.get_serializer(dispute)

        # Cache for 10 minutes
        cache.set(cache_key, serializer.data, 600)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Retrieved dispute {dispute_id} in {duration:.2f}ms")

        return self.success_response(data=serializer.data)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def resolve(self, request, pk=None):
        """Resolve a dispute (admin/staff only)"""
        if not request.user.is_staff:
            return self.error_response(
                message="Only staff can resolve disputes",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        dispute = self.get_object()
        serializer = DisputeResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            resolved_dispute = DisputeService.resolve_dispute(
                dispute_id=dispute.id,
                resolver_user=request.user,
                status=serializer.validated_data["status"],
                resolution_note=serializer.validated_data.get("resolution_note", ""),
            )

            response_serializer = DisputeDetailSerializer(resolved_dispute)
            return self.success_response(data=response_serializer.data)

        except ValidationError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"])
    def my_disputes(self, request):
        """Get current user's disputes"""
        status_filter = request.query_params.get("status")

        disputes = DisputeService.get_user_disputes(request.user, status_filter)
        serializer = DisputeListSerializer(disputes, many=True)

        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get dispute statistics (admin only)."""
        try:
            stats = DisputeService.get_stats(request.user)
        except PermissionError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_403_FORBIDDEN
            )

        return self.success_response(data=stats)

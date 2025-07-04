from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from apps.core.utils.cache_manager import CacheKeyManager
from apps.disputes.utils.rate_limiting import DisputeRateThrottle
from .models import Dispute, DisputeStatus
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


class DisputeViewSet(viewsets.ModelViewSet):
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

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        """Get dispute details with caching"""
        dispute_id = kwargs.get("pk")
        cache_key = CacheKeyManager.make_key("dispute", "detail", id=dispute_id)

        # Try cache first
        from django.core.cache import cache

        cached_dispute = cache.get(cache_key)
        if cached_dispute is not None:
            logger.info(f"Retrieved dispute {dispute_id} from cache")
            return Response(cached_dispute)

        start_time = timezone.now()

        dispute = self.get_object()
        serializer = self.get_serializer(dispute)

        # Cache for 10 minutes
        cache.set(cache_key, serializer.data, 600)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Retrieved dispute {dispute_id} in {duration:.2f}ms")

        return Response(serializer.data)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def resolve(self, request, pk=None):
        """Resolve a dispute (admin/staff only)"""
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff can resolve disputes"},
                status=status.HTTP_403_FORBIDDEN,
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
            return Response(response_serializer.data)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def my_disputes(self, request):
        """Get current user's disputes"""
        status_filter = request.query_params.get("status")

        disputes = DisputeService.get_user_disputes(request.user, status_filter)
        serializer = DisputeListSerializer(disputes, many=True)

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get dispute statistics (admin only)"""
        if not request.user.is_staff:
            return Response(
                {"error": "Only staff can view statistics"},
                status=status.HTTP_403_FORBIDDEN,
            )

        cache_key = CacheKeyManager.make_key(
            "dispute", "stats", user_id=request.user.id
        )

        # Try cache first
        from django.core.cache import cache

        cached_stats = cache.get(cache_key)
        if cached_stats is not None:
            logger.info("Retrieved dispute stats from cache")
            return Response(cached_stats)

        start_time = timezone.now()

        stats = {
            "total_disputes": Dispute.objects.count(),
            "open_disputes": Dispute.objects.filter(
                status=DisputeStatus.OPENED
            ).count(),
            "resolved_for_buyer": Dispute.objects.filter(
                status=DisputeStatus.RESOLVED_BUYER
            ).count(),
            "resolved_for_seller": Dispute.objects.filter(
                status=DisputeStatus.RESOLVED_SELLER
            ).count(),
            "closed_disputes": Dispute.objects.filter(
                status=DisputeStatus.CLOSED
            ).count(),
        }

        # Cache for 30 minutes
        cache.set(cache_key, stats, 1800)

        duration = (timezone.now() - start_time).total_seconds() * 1000
        logger.info(f"Generated dispute stats in {duration:.2f}ms")

        return Response(stats)

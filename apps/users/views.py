import logging
from django.conf import settings
from django.db.models import Count, Q, Prefetch, Sum
from django.core.cache import cache


from apps.core.views import BaseResponseMixin, BaseViewSet
from rest_framework import permissions, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.users.utils.total_buy import get_buyer_analytics_summary
from apps.users.utils.user_cache import (
    get_cached_user_profile,
    set_user_profile_cache,
    invalidate_user_profile_cache,
)


# Import your optimized service
from .services.seller_analytics import SellerAnalyticsService


from apps.transactions.models.transaction import EscrowTransaction
from apps.users.models.user_profile import UserProfile
from apps.users.serializers import (
    PublicUserProfileSerializer,
    UserAddressSerializer,
    UserProfileSerializer,
)
from apps.users.models.user_address import UserAddress

logger = logging.getLogger(__name__)


class UserAddressViewSet(BaseViewSet):
    """ViewSet for managing user addresses"""

    CACHE_TTL = 60 * 30  # 30 minutes cache

    queryset = UserAddress.objects.all()
    serializer_class = UserAddressSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        user_id = kwargs.get(
            "user_id",
            self.request.user.id if self.request.user.is_authenticated else "anonymous",
        )
        return f"address:{view_name}:{kwargs.get('pk', '')}:{user_id}"

    def get_queryset(self):
        user = self.request.user
        return UserAddress.objects.filter(user=user)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        address = serializer.save(user=self.request.user)
        # Clear list cache
        cache.delete(self.get_cache_key("list", user_id=address.user.id))

    def perform_update(self, serializer):
        address = serializer.instance
        # Clear caches
        cache_keys = [
            self.get_cache_key("detail", pk=address.pk),
            self.get_cache_key("list", user_id=address.user.id),
        ]
        cache.delete_many(cache_keys)
        serializer.save()


class UserProfileViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
    BaseResponseMixin,
):
    """
    - GET /users/             → list all profiles (public)
    - GET /users/<uuid>/      → retrieve one (public, read-only)
    - GET|PATCH|PUT /users/me/→ current user (auth required)
    - NO POST, PUT, PATCH, DELETE on /users/<uuid>/
    """

    lookup_field = "user_id"
    lookup_url_kwarg = "user_id"

    queryset = (
        UserProfile.objects.select_related("user")
        .prefetch_related(
            Prefetch(
                "user__seller_transactions",
                queryset=EscrowTransaction.objects.order_by("-created_at")[:21],
                to_attr="recent_sales",
            )
        )
        .annotate(
            completed_as_seller=Count(
                "user__seller_transactions",
                filter=Q(user__seller_transactions__status="completed"),
            ),
            completed_as_buyer=Count(
                "user__buyer_transactions",
                filter=Q(user__buyer_transactions__status="completed"),
            ),
            total_as_buyer=Sum(
                "user__buyer_transactions__total_amount",
                filter=Q(user__buyer_transactions__status="completed"),
            ),
        )
    )

    def get_serializer_class(self):
        if self.action == "me":
            return UserProfileSerializer
        if self.action in ["list", "retrieve"]:
            return PublicUserProfileSerializer
        return UserProfileSerializer

    def get_permissions(self):
        # only /users/me/ needs auth
        if self.action == "me":
            return [IsAuthenticated()]
        return []

    @action(detail=False, methods=["get", "patch", "put"], url_path="me")
    def me(self, request):
        """
        GET    /users/me/ → view own profile
        PATCH  /users/me/ → partial update
        PUT    /users/me/ → full update
        """
        if not request.user.is_authenticated:
            raise NotAuthenticated("Authentication required")

        user_id = request.user.id

        if request.method == "GET":
            # Try to get from cache first
            cached_data = get_cached_user_profile(user_id)
            if cached_data:
                return self.success_response(data=cached_data)

            # If not in cache, get from database
            profile = self.queryset.get(user=request.user)
            serialized_data = self.get_serializer(profile).data

            # Cache for 15 minutes
            set_user_profile_cache(user_id, serialized_data)

            return self.success_response(data=serialized_data)

        # For PATCH/PUT, update the profile and invalidate cache
        profile = self.queryset.get(user=request.user)
        partial = request.method == "PATCH"
        serializer = self.get_serializer(profile, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Invalidate cache after update
        invalidate_user_profile_cache(user_id)

        # Optionally, set the new data in cache immediately
        set_user_profile_cache(user_id, serializer.data)

        return self.success_response(data=serializer.data)


CACHE_TTL = getattr(settings, "CACHE_TTL", 60 * 5)  # default 5 minutes


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def seller_analytics_view(request):
    """
    Function-based endpoint to return comprehensive seller analytics.
    Caches results per-user to reduce DB hits.
    """
    user = request.user
    cache_key = f"seller_analytics_{user.id}"
    data = cache.get(cache_key)
    if data is None:
        service = SellerAnalyticsService(user)
        data = service.get_comprehensive_seller_analytics()
        cache.set(cache_key, data, CACHE_TTL)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def buyer_analytics_view(request):
    """
    Function-based endpoint to return buyer analytics summary.
    Caches results per-user to reduce DB hits.
    """
    user = request.user
    cache_key = f"buyer_analytics_{user.id}"
    summary = cache.get(cache_key)
    if summary is None:
        summary = get_buyer_analytics_summary(user)
        cache.set(cache_key, summary, CACHE_TTL)
    return Response(summary)

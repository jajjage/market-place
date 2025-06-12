import logging
from django.db.models import Count, Sum, Q

from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie


from apps.core.views import BaseViewSet
from rest_framework import viewsets, permissions

from apps.users.models.base import CustomUser
from apps.users.serializers import (
    PublicUserSerializer,
    UserAddressSerializer,
)
from apps.users.models.user_address import UserAddress

logger = logging.getLogger(__name__)


@extend_schema(tags=["User Address"])
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

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
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


@extend_schema(tags=["User Profile"])
class UserProfileViewSet(viewsets.ReadOnlyModelViewSet, BaseViewSet):
    """ViewSet for user profiles with caching"""

    CACHE_TTL = 60 * 15  # 15 minutes cache

    serializer_class = PublicUserSerializer
    permission_classes = []

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        user_id = kwargs.get(
            "user_id",
            self.request.user.id if self.request.user.is_authenticated else "anonymous",
        )
        return f"profile:{view_name}:{kwargs.get('pk', '')}:{user_id}"

    def get_queryset(self):
        return (
            CustomUser.objects.select_related("profile")
            .filter(profile__isnull=False)
            .annotate(
                # Annotate on CustomUser, not UserProfile
                completed_sales_count=Count(
                    "seller_transactions",
                    filter=Q(seller_transactions__status="completed"),
                ),
                completed_purchases_count=Count(
                    "buyer_transactions",
                    filter=Q(buyer_transactions__status="completed"),
                ),
                total_sales_amount=Sum(
                    "seller_transactions__amount",
                    filter=Q(seller_transactions__status="completed"),
                ),
            )
        )

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_object(self):
        if self.kwargs.get("pk") == "me":
            return self.request.user
        return super().get_object()

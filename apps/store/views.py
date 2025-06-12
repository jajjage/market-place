from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from apps.core.views import BaseViewSet
from rest_framework import permissions

from apps.store.models import UserStore
from apps.store.serializers import UserStoreSerializer


@extend_schema(tags=["User Store"])
class UserStoreViewSet(BaseViewSet):
    """ViewSet for managing user stores"""

    CACHE_TTL = 60 * 30  # 30 minutes cache

    queryset = UserStore.objects.all()
    serializer_class = UserStoreSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        user_id = kwargs.get(
            "user_id",
            self.request.user.id if self.request.user.is_authenticated else "anonymous",
        )
        return f"store:{view_name}:{kwargs.get('pk', '')}:{user_id}"

    def get_queryset(self):
        user = self.request.user
        return UserStore.objects.filter(user=user)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        store = serializer.save(user=self.request.user)
        # Clear list cache
        cache.delete(self.get_cache_key("list", user_id=store.user.id))

    def perform_update(self, serializer):
        store = serializer.instance
        # Clear caches
        cache_keys = [
            self.get_cache_key("detail", pk=store.pk),
            self.get_cache_key("list", user_id=store.user.id),
        ]
        cache.delete_many(cache_keys)
        serializer.save()

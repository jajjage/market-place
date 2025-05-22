from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from apps.comments.models import UserRating
from apps.core.permissions import IsOwnerOrReadOnly
from apps.core.views import BaseViewSet
from rest_framework import permissions

from apps.comments.serializers import UserRatingSerializer


@extend_schema(tags=["User Ratings"])
class UserRatingViewSet(BaseViewSet):
    """ViewSet for managing user ratings"""

    CACHE_TTL = 60 * 15  # 15 minutes cache

    queryset = UserRating.objects.all()
    serializer_class = UserRatingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        user_id = kwargs.get(
            "user_id",
            self.request.user.id if self.request.user.is_authenticated else "anonymous",
        )
        return f"rating:{view_name}:{kwargs.get('pk', '')}:{user_id}"

    def get_queryset(self):
        user = self.request.user
        return UserRating.objects.filter(to_user=user) | UserRating.objects.filter(
            from_user=user
        )

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        rating = serializer.save(from_user=self.request.user)
        # Clear caches
        cache_keys = [
            self.get_cache_key("list", user_id=rating.from_user.id),
            self.get_cache_key("list", user_id=rating.to_user.id),
        ]
        cache.delete_many(cache_keys)

    def perform_update(self, serializer):
        rating = serializer.instance
        # Clear caches before update
        cache_keys = [
            self.get_cache_key("detail", pk=rating.pk),
            self.get_cache_key("list", user_id=rating.from_user.id),
            self.get_cache_key("list", user_id=rating.to_user.id),
        ]
        cache.delete_many(cache_keys)
        serializer.save()

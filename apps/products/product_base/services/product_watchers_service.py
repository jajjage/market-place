from apps.core.utils.cache_manager import CacheKeyManager
from django.core.cache import cache
from rest_framework.response import Response
from django.db.models import Value
from django.db.models.functions import Concat


class ProductWatchersService:
    @staticmethod
    def get_watchers(view, request, pk=None):
        cache_key = CacheKeyManager.make_key("base", "watchers", id=pk)
        cached_data = cache.get(cache_key)
        if cached_data:
            view.logger.info(f"Cache HIT for watchers: {cache_key}")
            return view.success_response(data=cached_data)
        product = view.get_object()
        if product.seller != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to view this information."},
                status=403,
            )
        watchers = product.watchers.select_related("user")
        watcher_data = {
            "count": watchers.count(),
            "recent_additions": (
                watchers.annotate(
                    full_name=Concat("user__first_name", Value(" "), "user__last_name")
                )
                .order_by("-added_at")[:5]
                .values("user_id", "user__email", "full_name", "added_at")
            ),
        }
        cache.set(cache_key, watcher_data, view.CACHE_TTL)
        view.logger.info(f"Cached watchers: {cache_key}")
        return view.success_response(data=watcher_data)

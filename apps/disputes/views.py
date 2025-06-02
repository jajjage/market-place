from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie

from apps.core.permissions import UserTypePermission
from apps.core.views import BaseViewSet
from apps.disputes.models import Dispute
from apps.disputes.serializers import DisputeSerializer


class DisputeViewSet(BaseViewSet):
    """
    ViewSet for handling transaction disputes.
    """

    CACHE_TTL = 60 * 5  # 5 minutes cache

    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [UserTypePermission]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        return (
            Dispute.objects.filter(opened_by=user)
            | Dispute.objects.filter(transaction__seller=user)
            | Dispute.objects.filter(transaction__buyer=user)
        )

    def get_cache_key(self, view_name, **kwargs):
        """Generate a cache key for the view"""
        user_id = kwargs.get(
            "user_id",
            self.request.user.id if self.request.user.is_authenticated else "anonymous",
        )
        return f"dispute:{view_name}:{kwargs.get('pk', '')}:{user_id}"

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(CACHE_TTL))
    @method_decorator(vary_on_cookie)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_update(self, serializer):
        """Clear cache when dispute is updated"""
        dispute = serializer.instance
        cache_keys = [
            self.get_cache_key("detail", pk=dispute.pk),
            self.get_cache_key("list", user_id=dispute.opened_by.id),
            self.get_cache_key("list", user_id=dispute.transaction.buyer.id),
            self.get_cache_key("list", user_id=dispute.transaction.seller.id),
        ]
        cache.delete_many(cache_keys)
        return super().perform_update(serializer)

    def perform_create(self, serializer):
        """Clear relevant caches when new dispute is created"""
        dispute = serializer.save()
        cache_keys = [
            self.get_cache_key("list", user_id=dispute.opened_by.id),
            self.get_cache_key("list", user_id=dispute.transaction.buyer.id),
            self.get_cache_key("list", user_id=dispute.transaction.seller.id),
        ]
        cache.delete_many(cache_keys)
        return dispute

import logging
from rest_framework import status, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from apps.core.permissions import (
    BuyerTransaction,
    IsTransactionParticipantOrStaff,
    SellerTransaction,
)
from apps.core.views import BaseViewSet
from apps.transactions.models import (
    EscrowTransaction,
)
from rest_framework.decorators import action
from apps.transactions.services.transaction_list_service import TransactionListService
from apps.transactions.utils.rate_limiting import (
    EscrowTransactionCreateRateThrottle,
    EscrowTransactionListRateThrottle,
    EscrowTransactionMyPurchaseRateThrottle,
    EscrowTransactionMySaleRateThrottle,
    EscrowTransactionTrackRateThrottle,
    EscrowTransactionUpdateRateThrottle,
)

from .serializers import (
    EscrowTransactionDetailSerializer,
    EscrowTransactionListSerializer,
    EscrowTransactionTrackingSerializer,
)
from apps.products.product_inventory.services import InventoryService
from .utils.transaction_filters import TransactionFilter
from .utils.statuses import is_status_change_allowed


class EscrowTransactionViewSet(BaseViewSet):
    """
    ViewSet for managing escrow transactions.
    Buyers can view their purchases, sellers can view their sales.
    Tracking functionality is available to both parties involved in a transaction.
    """

    logger = logging.getLogger("transactions_performance")
    CACHE_TTL = 60 * 5  # 5 minutes cache
    TRACK_CACHE_TTL = 60 * 2  # 2 minutes cache for tracking info

    permission_classes = [IsAuthenticatedOrReadOnly, IsTransactionParticipantOrStaff]
    filterset_class = TransactionFilter
    throttle_classes = []
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["tracking_id", "product__title", "buyer__email", "seller__email"]
    ordering_fields = ["created_at", "updated_at", "status", "amount"]
    ordering = ["-created_at"]

    def get_throttles(self):
        if self.action == "list":
            throttle_classes = [EscrowTransactionListRateThrottle]
        else:
            throttle_classes = [EscrowTransactionCreateRateThrottle]
        return [throttle() for throttle in throttle_classes]

    def get_queryset(self):
        """Base queryset - only return transactions where user is involved"""
        user = self.request.user
        if user.is_staff:
            return EscrowTransaction.objects.all()

        # Since any user can buy/sell, return transactions where user is involved
        return EscrowTransaction.objects.filter(Q(buyer=user) | Q(seller=user))

    def get_serializer_context(self):
        """
        Ensures the request context is passed to the serializer.
        This is often implicitly done by ModelViewSet, but explicitly defining it
        is good practice or necessary for custom ViewSets.
        """
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_serializer_class(self):
        """Return different serializers based on the action."""
        if self.action == "list":
            return EscrowTransactionListSerializer
        elif self.action == "track":
            return EscrowTransactionTrackingSerializer
        return EscrowTransactionDetailSerializer

    def list(self, request):
        """List transactions using service"""
        queryset = self.get_queryset()
        status_filter = request.query_params.get("status", None)
        search_query = request.query_params.get("search", "")

        offset = request.query_params.get("offset", 0)
        limit = request.query_params.get("limit", 25)
        result = TransactionListService.get_user_all_transactions(
            user=request.user,
            queryset=queryset,
            status_filter=status_filter,
            search_query=search_query,
            ordering=None,
            offset=int(offset),
            limit=int(limit),
        )

        # Handle pagination if needed
        if not result["from_cache"]:
            # If data is not from cache, apply pagination
            page = self.paginate_queryset(result["data"])
            if page is not None:
                return self.get_paginated_response(page)

        return self.success_response(
            data=result["data"],
            # meta={'from_cache': result['from_cache']}
        )

    @action(
        detail=False,
        methods=["get"],
        throttle_classes=[EscrowTransactionMySaleRateThrottle],
        permission_classes=[SellerTransaction],
    )
    def my_sales(self, request):
        """Return only the current user's sales transactions using service"""
        queryset = self.get_queryset()
        status_filter = request.query_params.get("status")

        result = TransactionListService.get_user_sales(
            user=request.user, queryset=queryset, status_filter=status_filter
        )

        # Handle pagination
        if not result["from_cache"]:
            page = self.paginate_queryset(result["data"])
            if page is not None:
                return self.get_paginated_response(page)

        return self.success_response(
            data=result["data"],
            # meta={'from_cache': result['from_cache']}
        )

    @action(
        detail=False,
        url_path="my-purchases",
        methods=["get"],
        throttle_classes=[EscrowTransactionMyPurchaseRateThrottle],
        permission_classes=[BuyerTransaction],
    )
    def my_purchases(self, request):
        """Return only the current user's purchase transactions using service"""
        queryset = self.get_queryset()
        status_filter = request.query_params.get("status")

        result = TransactionListService.get_user_purchases(
            user=request.user, queryset=queryset, status_filter=status_filter
        )

        # Handle pagination
        if not result["from_cache"]:
            page = self.paginate_queryset(result["data"])
            if page is not None:
                return self.get_paginated_response(page)

        return self.success_response(
            data=result["data"],
            # meta={'from_cache': result['from_cache']}
        )

    @action(
        detail=False,
        url_path=r"track/(?P<tracking_id>[^/.]+)",
        methods=["get"],
        throttle_classes=[EscrowTransactionTrackRateThrottle],
    )
    def track(self, request, tracking_id=None):
        """
        Track an escrow transaction by its tracking ID.
        This endpoint is accessible to both buyers and sellers involved in the transaction.
        """
        try:
            data, from_cache = TransactionListService.get_tracking(
                tracking_id, request.user
            )
        except PermissionDenied as e:
            return self.error_response(str(e), status=403)
        return self.success_response(data=data)

    @action(
        detail=True,
        url_path="update-status",
        methods=["post"],
        throttle_classes=[EscrowTransactionUpdateRateThrottle],
    )
    def update_status(self, request, pk=None):
        """
        Update the status of an escrow transaction.
        Different status updates have different permission requirements.
        """
        transaction = self.get_object()
        new_status = request.data.get("status")
        notes = request.data.get("notes", "")
        tracking_number = request.data.get("tracking_number")
        shipping_carrier = request.data.get("shipping_carrier")

        if not is_status_change_allowed(transaction, new_status, request.user):
            return self.error_response(
                message="You are not authorized to change the status to this value.",
                status=status.HTTP_403_FORBIDDEN,
            )

        updated_transaction = InventoryService.update_escrow_transaction_status(
            escrow_transaction=transaction,
            status=new_status,
            user=request.user,
            notes=notes,
            tracking_number=tracking_number,
            shipping_carrier=shipping_carrier,
        )

        serializer = self.get_serializer(updated_transaction)

        TransactionListService.invalidate_transaction_caches(transaction)

        return self.success_response(data=serializer.data)

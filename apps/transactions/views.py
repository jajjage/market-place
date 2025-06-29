import logging
from rest_framework import status, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
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
from apps.transactions.services.escrow_services import (
    EscrowTransactionService,
    EscrowTransactionUtility,
)
from .utils.transaction_filters import TransactionFilter
from .utils.validate_actions import (
    get_other_party_info,
    get_required_fields_for_status,
    get_action_warnings,
    get_status_metadata,
)


class EscrowTransactionViewSet(BaseViewSet):
    """
    ViewSet for managing escrow transactions.
    Buyers can view their purchases, sellers can view their sales.
    Tracking functionality is available to both parties involved in a transaction.
    """

    logger = logging.getLogger("transactions_performance")
    CACHE_TTL = 60 * 5  # 5 minutes cache
    TRACK_CACHE_TTL = 60 * 2  # 2 minutes cache for tracking info

    permission_classes = [IsAuthenticated, IsTransactionParticipantOrStaff]
    filterset_class = TransactionFilter
    throttle_classes = []
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["tracking_id", "product__title", "buyer__email", "seller__email"]
    ordering_fields = ["created_at", "updated_at", "status", "price"]
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
        detail=True,  # Changed to True since you're updating a specific transaction
        url_path="update-status",
        methods=["post"],
        throttle_classes=[EscrowTransactionUpdateRateThrottle],
    )
    def update_status(self, request, pk=None):
        """
        Enhanced status update endpoint with comprehensive validation
        """
        try:
            transaction = self.get_object()

            # Extract and validate request data
            new_status = request.data.get("status")
            if not new_status:
                return self.error_response(
                    message="Status is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            # if not transaction.status != new_status:
            #     return self.error_response(
            #         message=f"Status is already in: {new_status}",
            #         status_code=status.HTTP_400_BAD_REQUEST,
            #     )

            notes = request.data.get("notes", "")
            tracking_number = request.data.get("tracking_number")  # Fixed field name
            shipping_carrier = request.data.get("shipping_carrier")

            # Update transaction using the service
            updated_transaction = (
                EscrowTransactionService.update_escrow_transaction_status(
                    escrow_transaction=transaction,
                    new_status=new_status,
                    user=request.user,
                    notes=notes,
                    tracking_number=tracking_number,
                    shipping_carrier=shipping_carrier,
                )
            )

            # Serialize the response
            serializer = self.get_serializer(
                updated_transaction, context={"request": request}
            )

            # Invalidate caches
            TransactionListService.invalidate_transaction_caches(transaction)

            return self.success_response(
                data=serializer.data,
                message=f"Transaction status updated to {new_status}",
            )

        except ValidationError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            self.logger.error(f"Unexpected error updating transaction status: {str(e)}")
            return self.error_response(
                message="An unexpected error occurred",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        url_path="available-actions",
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def available_actions(self, request, pk=None):
        """
        Get available actions for the current user on a specific transaction

        Returns:
            - available_actions: List of actions user can perform
            - user_role: User's role in this transaction (buyer/seller/staff)
            - current_status: Current transaction status
            - transaction_info: Basic transaction details
        """
        try:
            transaction = self.get_object()

            # Get available actions using the utility
            actions_data = EscrowTransactionUtility.get_available_actions(
                transaction, request.user
            )

            # Add additional transaction context
            response_data = {
                **actions_data,
                "transaction_info": {
                    "id": transaction.id,
                    "current_status": transaction.status,
                    "buyer_id": transaction.buyer.id if transaction.buyer else None,
                    "seller_id": transaction.seller.id if transaction.seller else None,
                    "amount": (
                        str(transaction.price)
                        if hasattr(transaction, "price")
                        else None
                    ),
                    "created_at": (
                        transaction.created_at.isoformat()
                        if hasattr(transaction, "created_at")
                        else None
                    ),
                },
                "status_metadata": get_status_metadata(transaction),
            }

            return self.success_response(data=response_data)
        except Exception as e:
            raise e
            # return self.error_response(
            #     message=f"Error fetching available actions: {str(e)}",
            #     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # )

    @action(
        detail=False,
        url_path="my-transactions-actions",
        methods=["get"],
        permission_classes=[IsAuthenticated],
    )
    def my_transactions_actions(self, request):
        """
        Get available actions for all transactions where the user is a participant
        Useful for dashboard views showing actionable items
        """
        try:
            # Get transactions where user is buyer or seller
            # Get transactions where user is buyer or seller
            user_transactions = self.get_queryset().select_related("buyer", "seller")
            # ----------------------------------------------------------
            # We may use this a list of transaction with caching like this one
            # user_transactions = TransactionListService.get_user_all_transactions(user=request.user, queryset=self.queryset)
            # ------------------------------------------------------

            transactions_with_actions = []

            for transaction in user_transactions:
                actions_data = EscrowTransactionUtility.get_available_actions(
                    transaction, request.user
                )

                # Only include transactions that have available actions
                if actions_data["available_actions"]:
                    transaction_data = {
                        "transaction_id": transaction.id,
                        "current_status": transaction.status,
                        "user_role": actions_data["user_role"],
                        "available_actions": actions_data["available_actions"],
                        "requires_attention": len(actions_data["available_actions"])
                        > 0,
                        "transaction_summary": {
                            "amount": (
                                str(transaction.price)
                                if hasattr(transaction, "price")
                                else None
                            ),
                            "other_party": get_other_party_info(
                                transaction, request.user
                            ),
                            "created_at": (
                                transaction.created_at.isoformat()
                                if hasattr(transaction, "created_at")
                                else None
                            ),
                        },
                    }
                    transactions_with_actions.append(transaction_data)

            return self.success_response(
                data={
                    "actionable_transactions": transactions_with_actions,
                    "total_count": len(transactions_with_actions),
                    "user_id": request.user.id,
                }
            )

        except Exception as e:
            return self.error_response(
                message=f"Error fetching user transactions: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=True,
        url_path="validate-action",
        methods=["post"],
        permission_classes=[IsAuthenticated],
    )
    def validate_action(self, request, pk=None):
        """
        Validate if a specific action can be performed without actually performing it
        Useful for frontend validation before showing confirmation dialogs
        """
        try:
            transaction = self.get_object()
            proposed_status = request.data.get("status")

            if not proposed_status:
                return self.error_response(
                    message="Status is required for validation",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Check if action is allowed
            is_allowed, reason = EscrowTransactionService.is_status_change_allowed(
                transaction, proposed_status, request.user
            )

            # Check requirements
            is_valid, validation_reason = (
                EscrowTransactionService.validate_status_requirements(
                    transaction,
                    proposed_status,
                    tracking_number=request.data.get("tracking_number"),
                    shipping_carrier=request.data.get("shipping_carrier"),
                )
            )

            validation_result = {
                "is_allowed": is_allowed and is_valid,
                "permission_check": {"allowed": is_allowed, "reason": reason},
                "requirement_check": {"valid": is_valid, "reason": validation_reason},
                "required_fields": get_required_fields_for_status(proposed_status),
                "warnings": get_action_warnings(transaction, proposed_status),
            }

            return self.success_response(data=validation_result)

        except Exception as e:
            return self.error_response(
                message=f"Error validating action: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

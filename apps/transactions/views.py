from django_filters import rest_framework as filters
from django.shortcuts import get_object_or_404
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from apps.core.permissions import UserTypePermission
from apps.core.views import BaseViewSet
from apps.transactions.models.transaction_dispute import Dispute
from .models.escrow_transactions import EscrowTransaction
from rest_framework.decorators import action
from rest_framework.response import Response
from .models.transaction_history import TransactionHistory
from .serializers import (
    DisputeSerializer,
    EscrowTransactionDetailSerializer,
    EscrowTransactionListSerializer,
    EscrowTransactionTrackingSerializer,
    TransactionHistorySerializer,
    ProductTrackingSerializer,
)
from apps.products.services import InventoryService


class EscrowTransactionViewSet(BaseViewSet):
    """
    ViewSet for managing escrow transactions.
    Buyers can view their purchases, sellers can view their sales.
    Tracking functionality is available to both parties involved in a transaction.
    """

    queryset = EscrowTransaction.objects.all()
    permission_classes = [UserTypePermission]
    permission_read_user_types = ["BUYER", "SELLER"]
    permission_write_user_types = ["SELLER"]  # Only sellers can initiate transactions
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    search_fields = ["tracking_id", "product__title", "buyer__email", "seller__email"]
    ordering_fields = ["created_at", "updated_at", "status", "amount"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return different serializers based on the action."""
        if self.action == "list":
            return EscrowTransactionListSerializer
        elif self.action == "track":
            return EscrowTransactionTrackingSerializer
        return EscrowTransactionDetailSerializer

    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        - Staff can see all transactions
        - Buyers can see their purchases
        - Sellers can see their sales
        """
        queryset = super().get_queryset()

        # For staff, return all transactions
        if self.request.user.is_staff:
            return queryset

        # For regular users, return only their transactions
        user_type = getattr(self.request.user, "user_type", None)
        if user_type == "BUYER":
            return queryset.filter(buyer=self.request.user)
        elif user_type == "SELLER":
            return queryset.filter(seller=self.request.user)

        # For users without a specific type, return no results
        return queryset.none()

    @action(detail=False, methods=["get"])
    def my_sales(self, request):
        """Return only the current user's sales transactions."""
        # Only sellers should access this
        if getattr(request.user, "user_type", None) != "SELLER":
            return Response(
                {"detail": "Only sellers can view sales."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = self.get_queryset().filter(seller=request.user)

        # Filter by status if provided
        status_param = request.query_params.get("status", None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["get"])
    def my_purchases(self, request):
        """Return only the current user's purchase transactions."""
        # Only buyers should access this
        if getattr(request.user, "user_type", None) != "BUYER":
            return Response(
                {"detail": "Only buyers can view purchases."},
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = self.get_queryset().filter(buyer=request.user)

        # Filter by status if provided
        status_param = request.query_params.get("status", None)
        if status_param:
            queryset = queryset.filter(status=status_param)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, url_path=r"track/(?P<tracking_id>[^/.]+)", methods=["get"])
    def track(self, request, tracking_id=None):
        """
        Track an escrow transaction by its tracking ID.
        This endpoint is accessible to both buyers and sellers involved in the transaction.
        """
        # Find the transaction by tracking_id
        transaction = get_object_or_404(EscrowTransaction, tracking_id=tracking_id)

        # Check if user is authorized to view this transaction
        if not request.user.is_staff and request.user not in [
            transaction.buyer,
            transaction.seller,
        ]:
            return Response(
                {"detail": "You do not have permission to track this transaction."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get transaction history
        history = TransactionHistory.objects.filter(transaction=transaction).order_by(
            "timestamp"
        )

        # Get transaction details
        serializer = self.get_serializer(transaction)
        data = serializer.data

        # Add history data
        history_data = TransactionHistorySerializer(history, many=True).data
        data["history"] = history_data

        # Add product details
        data["product_details"] = ProductTrackingSerializer(transaction.product).data

        # Add estimated delivery information if applicable
        if transaction.status in ["shipped", "delivered"]:
            # You could integrate with shipping APIs here for real-time tracking
            data["shipping_info"] = {
                "tracking_number": transaction.tracking_number,
                "shipping_carrier": transaction.shipping_carrier,
                "status_updates": history_data,
            }

        return self.success_response(data=data)

    @action(detail=True, methods=["post"])
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

        # Validate the status transition is allowed for this user
        if not self._is_status_change_allowed(transaction, new_status, request.user):
            return Response(
                {
                    "detail": "You are not authorized to change the status to this value."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Use the inventory service to update the status
        updated_transaction = InventoryService.update_escrow_transaction_status(
            escrow_transaction=transaction,
            status=new_status,
            user=request.user,
            notes=notes,
            tracking_number=tracking_number,
            shipping_carrier=shipping_carrier,
        )

        serializer = self.get_serializer(updated_transaction)
        return self.success_response(data=serializer.data)

    def _is_status_change_allowed(self, transaction, new_status, user):
        """
        Helper method to determine if a status change is allowed.
        Different roles can perform different status changes.
        """
        # Staff can change to any status
        if user.is_staff:
            return True

        # Get user type
        user_type = getattr(user, "user_type", None)

        # Check if user is involved in the transaction
        is_buyer = user == transaction.buyer
        is_seller = user == transaction.seller

        # Define allowed status transitions by role
        allowed_transitions = {
            "BUYER": {
                "initiated": ["cancelled"] if is_buyer else [],
                "payment_received": [] if is_buyer else [],
                "shipped": ["delivered"] if is_buyer else [],
                "delivered": ["inspection"] if is_buyer else [],
                "inspection": ["completed", "disputed"] if is_buyer else [],
                "disputed": [] if is_buyer else [],  # Admin handles disputes
                "completed": [] if is_buyer else [],  # Final state
                "refunded": [] if is_buyer else [],  # Final state
                "cancelled": [] if is_buyer else [],  # Final state
            },
            "SELLER": {
                "initiated": ["payment_received", "cancelled"] if is_seller else [],
                "payment_received": ["shipped"] if is_seller else [],
                "shipped": [] if is_seller else [],  # Buyer confirms delivery
                "delivered": [] if is_seller else [],  # Buyer starts inspection
                "inspection": [] if is_seller else [],  # Buyer approves or disputes
                "disputed": [] if is_seller else [],  # Admin handles disputes
                "completed": [] if is_seller else [],  # Final state
                "refunded": [] if is_seller else [],  # Final state
                "cancelled": [] if is_seller else [],  # Final state
            },
        }

        # If user type is not defined or user is not involved in transaction
        if user_type not in allowed_transitions:
            return False

        # Check if the current status exists in the allowed transitions
        if transaction.status not in allowed_transitions[user_type]:
            return False

        # Check if the new status is in the allowed transitions for this user type and current status
        return new_status in allowed_transitions[user_type][transaction.status]


class DisputeViewSet(BaseViewSet):
    """
    ViewSet for handling transaction disputes.
    """

    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [UserTypePermission]
    permission_user_types = ["SELLER", "BUYER"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        return (
            Dispute.objects.filter(opened_by=user)
            | Dispute.objects.filter(transaction__seller=user)
            | Dispute.objects.filter(transaction__buyer=user)
        )

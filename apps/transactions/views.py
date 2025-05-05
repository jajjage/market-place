from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from apps.core.permissions import UserTypePermission
from apps.core.views import BaseViewSet
from .models.escrow_transactions import EscrowTransaction
from .models.transaction_dispute import Dispute
from .models.transaction_history import TransactionHistory
from .serializers import (
    EscrowTransactionCreateSerializer,
    EscrowTransactionDetailSerializer,
    EscrowTransactionStatusUpdateSerializer,
    DisputeSerializer,
    TransactionHistorySerializer,
)


class TransactionViewSet(BaseViewSet):
    """
    ViewSet for handling escrow transactions.
    """

    queryset = EscrowTransaction.objects.all()
    serializer_class = EscrowTransactionDetailSerializer
    permission_classes = [UserTypePermission]
    permission_user_types = ["SELLER", "BUYER"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        return EscrowTransaction.objects.filter(
            buyer=user
        ) | EscrowTransaction.objects.filter(seller=user)

    def get_serializer_class(self):
        if self.action == "create":
            return EscrowTransactionCreateSerializer
        if self.action == "update_status":
            return EscrowTransactionStatusUpdateSerializer
        return EscrowTransactionDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return self.send_response(
            data=serializer.data, message="Transactions retrieved successfully"
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return self.send_response(
            data=EscrowTransactionDetailSerializer(instance).data,
            message="Transaction created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return self.send_response(
            data=serializer.data, message="Transaction details retrieved successfully"
        )


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

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return self.send_response(
            data=serializer.data, message="Disputes retrieved successfully"
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return self.send_response(
            data=self.get_serializer(instance).data,
            message="Dispute created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return self.send_response(
            data=serializer.data, message="Dispute details retrieved successfully"
        )


class TransactionHistoryViewSet(BaseViewSet):
    """
    ViewSet for handling transaction history entries.
    """

    queryset = TransactionHistory.objects.all()
    serializer_class = TransactionHistorySerializer
    permission_classes = [UserTypePermission]
    permission_user_types = ["SELLER", "BUYER"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        user = self.request.user
        return TransactionHistory.objects.filter(
            transaction__buyer=user
        ) | TransactionHistory.objects.filter(transaction__seller=user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return self.send_response(
            data=serializer.data, message="Transaction history retrieved successfully"
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return self.send_response(
            data=serializer.data,
            message="History entry created successfully",
            status_code=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return self.send_response(
            data=serializer.data, message="History entry details retrieved successfully"
        )

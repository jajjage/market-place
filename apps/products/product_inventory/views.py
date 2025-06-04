from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from django.shortcuts import get_object_or_404
from django.db import transaction


from apps.core.permissions import IsOwnerOrReadOnly
from apps.products.product_base.models import Product
from .models import InventoryTransaction
from .serializers import (
    AddInventorySerializer,
    ActivateInventorySerializer,
    EscrowInventorySerializer,
    ReleaseEscrowSerializer,
    DeductInventorySerializer,
    InventoryTransactionSerializer,
)
from .services import InventoryService  # Import your existing service


class InventoryViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    ViewSet for inventory management operations
    """

    serializer_class = InventoryTransactionSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        """Filter transactions by product if product_id is provided"""
        queryset = InventoryTransaction.objects.select_related(
            "product", "created_by"
        ).all()

        product_id = self.request.query_params.get("product_id")
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        return queryset

    def get_product(self, product_id):
        """Helper method to get product and check permissions"""
        product = get_object_or_404(Product, id=product_id)

        # Check if user is the seller or has appropriate permissions
        if product.seller != self.request.user and not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You don't have permission to manage this product's inventory"
            )

        if not product.is_active:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cannot modify inventory for inactive product")

        return product

    @action(detail=False, methods=["post"], url_path="add")
    def add_inventory(self, request):
        """Add inventory to total"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        product = self.get_product(product_id)
        serializer = AddInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data["quantity"]
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.add_inventory(
                    product=product, quantity=quantity, user=request.user, notes=notes
                )

            if result:
                return Response(
                    {
                        "status": "success",
                        "total": result.total_inventory,
                        "available": result.available_inventory,
                        "in_escrow": result.in_escrow_inventory,
                    }
                )
            else:
                return Response(
                    {"status": "error", "message": "Failed to add inventory"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="activate")
    def activate_inventory(self, request):
        """Move inventory from total to available"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        product = self.get_product(product_id)
        serializer = ActivateInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data.get("quantity")
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.activate_inventory(
                    product=product, quantity=quantity, user=request.user, notes=notes
                )

            if result:
                return Response(
                    {
                        "status": "success",
                        "total": result.total_inventory,
                        "available": result.available_inventory,
                        "in_escrow": result.in_escrow_inventory,
                    }
                )
            else:
                return Response(
                    {"status": "error", "message": "No inventory to activate"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="escrow")
    def place_in_escrow(self, request):
        """Place inventory in escrow for transaction"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        product = self.get_product(product_id)
        serializer = EscrowInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data["quantity"]
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.place_in_escrow(
                    product=product, quantity=quantity, buyer=request.user, notes=notes
                )

            if result:
                product_result = result[0]
                transaction_tracking_id = result[1]

                return Response(
                    {
                        "status": "success",
                        "total": product_result.total_inventory,
                        "available": product_result.available_inventory,
                        "in_escrow": product_result.in_escrow_inventory,
                        "transaction_id": transaction_tracking_id.tracking_id,
                    }
                )
            else:
                return Response(
                    {"status": "error", "message": "Insufficient available inventory"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="release")
    def release_from_escrow(self, request):
        """Release inventory from escrow back to available"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        product = self.get_product(product_id)
        serializer = ReleaseEscrowSerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data["quantity"]
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.release_from_escrow(
                    product=product, quantity=quantity, user=request.user, notes=notes
                )

            if result:
                return Response(
                    {
                        "status": "success",
                        "total": result.total_inventory,
                        "available": result.available_inventory,
                        "in_escrow": result.in_escrow_inventory,
                    }
                )
            else:
                return Response(
                    {"status": "error", "message": "Insufficient inventory in escrow"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="deduct")
    def deduct_inventory(self, request):
        """Deduct inventory from escrow (completing a sale)"""
        product_id = request.data.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        product = self.get_product(product_id)
        serializer = DeductInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data["quantity"]
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.deduct_inventory(
                    product=product, quantity=quantity, user=request.user, notes=notes
                )

            if result:
                return Response(
                    {
                        "status": "success",
                        "total": result.total_inventory,
                        "available": result.available_inventory,
                        "in_escrow": result.in_escrow_inventory,
                    }
                )
            else:
                return Response(
                    {"status": "error", "message": "Failed to deduct inventory"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="status/(?P<product_id>[^/.]+)")
    def inventory_status(self, request, product_id=None):
        """Get current inventory status for a product"""
        product = get_object_or_404(Product, id=product_id)

        return Response(
            {
                "product_id": product.id,
                "product_title": product.title,
                "total": product.total_inventory,
                "available": product.available_inventory,
                "in_escrow": product.in_escrow_inventory,
                "status": "active" if product.is_active else "inactive",
            }
        )

    @action(detail=False, methods=["get"], url_path="history/(?P<product_id>[^/.]+)")
    def inventory_history(self, request, product_id=None):
        """Get inventory transaction history for a product"""
        product = get_object_or_404(Product, id=product_id)

        # Check permissions
        if product.seller != request.user and not request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You don't have permission to view this product's inventory history"
            )

        transactions = (
            InventoryTransaction.objects.filter(product=product)
            .select_related("created_by")
            .order_by("-created_at")
        )

        serializer = self.get_serializer(transactions, many=True)
        return Response(
            {
                "product_id": product.id,
                "product_title": product.title,
                "transactions": serializer.data,
            }
        )

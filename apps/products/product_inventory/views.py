from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework.permissions import IsAuthenticatedOrReadOnly
from apps.core.views import BaseResponseMixin
from apps.products.product_base.models import Product
from .models import InventoryTransaction
from .serializers import (
    AddInventorySerializer,
    ActivateInventorySerializer,
    EscrowInventorySerializer,
    InventoryTransactionSerializer,
)
from .services import InventoryService  # Import your existing service


class InventoryViewSet(
    GenericViewSet, ListModelMixin, RetrieveModelMixin, BaseResponseMixin
):
    """
    ViewSet for inventory management operations
    """

    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = InventoryTransactionSerializer

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

        if not product.status not in ["draft", "inactive", "sold"]:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"Cannot modify inventory for {product.status} product"
            )

        return product

    def get_product_escrow(self, product_id):
        """Helper method to get product and check permissions"""
        product = get_object_or_404(Product, id=product_id)

        # Check if user is the seller or has appropriate permissions
        if product.seller == self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You don't have permission to initiated transaction for this product"
            )

        if not product.is_active:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cannot modify inventory for inactive product")

        if not product.status not in ["draft", "inactive", "sold"]:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"Cannot modify inventory for {product.status} product"
            )

        return product

    @action(
        detail=False,
        methods=["post"],
        url_path="add",
    )
    def add_inventory(self, request):
        """Add inventory to total"""
        product_id = request.data.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
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
                return self.success_response(
                    data={
                        "total": result.total_inventory,
                        "available": result.available_inventory,
                        "in_escrow": result.in_escrow_inventory,
                    },
                    status_code=status.HTTP_200_OK,
                )
            else:
                return self.error_response(
                    message="Failed to add inventory",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="activate",
    )
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
                return self.success_response(
                    data={
                        "total": result.total_inventory,
                        "available": result.available_inventory,
                        "in_escrow": result.in_escrow_inventory,
                    },
                    status_code=status.HTTP_200_OK,
                )
            else:
                return self.error_response(
                    message="Failed to add inventory",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="place-in-escrow",
    )
    def place_in_escrow(self, request):
        """Place inventory in escrow for transaction"""
        product_id = request.data.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        product = self.get_product_escrow(product_id)
        serializer = EscrowInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data["quantity"]
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.place_in_escrow(
                    product=product,
                    quantity=quantity,
                    buyer=request.user,
                    currency=product.currency,
                    notes=notes,
                )

            if result:
                product_result, transaction_tracking_id, to_paid = result

                return self.success_response(
                    data={
                        "total": product_result.total_inventory,
                        "available": product_result.available_inventory,
                        "in_escrow": product_result.in_escrow_inventory,
                        "transaction_id": transaction_tracking_id.tracking_id,
                        "to_paid": f"${float(to_paid)}",
                        "items": quantity,
                    }
                )
            else:
                return self.error_response(
                    message="Failed to add inventory",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    # @action(detail=False, methods=["post"], url_path="release")
    # def release_from_escrow(self, request):
    #     """Release inventory from escrow back to available"""
    #     product_id = request.data.get("product_id")
    #     if not product_id:
    #         return Response(
    #             {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
    #         )

    #     product = self.get_product(product_id)
    #     serializer = ReleaseEscrowSerializer(data=request.data)

    #     if serializer.is_valid():
    #         quantity = serializer.validated_data["quantity"]
    #         notes = serializer.validated_data.get("notes", "")

    #         with transaction.atomic():
    #             result = InventoryService.release_from_escrow(
    #                 product=product, quantity=quantity, user=request.user, notes=notes
    #             )

    #         if result:
    #             return self.success_response(
    #                 data={
    #                     "total": result.total_inventory,
    #                     "available": result.available_inventory,
    #                     "in_escrow": result.in_escrow_inventory,
    #                 }
    #             )
    #         else:
    #             return self.error_response(
    #                 message="Failed to add inventory",
    #                 status_code=status.HTTP_400_BAD_REQUEST,
    #             )

    #     return self.error_response(
    #         message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
    #     )

    # @action(detail=False, methods=["post"], url_path="deduct")
    # def deduct_inventory(self, request):
    #     """Deduct inventory from escrow (completing a sale)"""
    #     product_id = request.data.get("product_id")
    #     if not product_id:
    #         return Response(
    #             {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
    #         )

    #     product = self.get_product(product_id)
    #     serializer = DeductInventorySerializer(data=request.data)

    #     if serializer.is_valid():
    #         quantity = serializer.validated_data["quantity"]
    #         notes = serializer.validated_data.get("notes", "")

    #         with transaction.atomic():
    #             result = InventoryService.deduct_inventory(
    #                 product=product, quantity=quantity, user=request.user, notes=notes
    #             )

    #         if result:
    #             return self.success_response(
    #                 data={
    #                     "total": result.total_inventory,
    #                     "available": result.available_inventory,
    #                     "in_escrow": result.in_escrow_inventory,
    #                 }
    #             )
    #         else:
    #             return self.error_response(
    #                 message="Failed to deduct inventory",
    #                 status_code=status.HTTP_400_BAD_REQUEST,
    #             )

    #     return self.error_response(
    #         message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
    #     )

    @action(detail=False, methods=["get"], url_path="status/(?P<product_id>[^/.]+)")
    def inventory_status(self, request, product_id=None):
        """Get current inventory status for a product"""
        product = get_object_or_404(Product, id=product_id)

        return self.success_response(
            data={
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
        return self.success_response(
            data={
                "product_id": product.id,
                "product_title": product.title,
                "transactions": serializer.data,
            }
        )

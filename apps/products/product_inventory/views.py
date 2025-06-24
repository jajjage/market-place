from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from rest_framework.permissions import IsAuthenticatedOrReadOnly
from apps.core.views import BaseResponseMixin
from apps.products.product_inventory.utils.escrow_item import (
    get_transaction_context,
    invalidate_caches,
    link_negotiation_to_transaction,
    prepare_response_data,
    validate_transaction_context,
)

from apps.products.product_variant.models import ProductVariant
from .models import InventoryTransaction
from .serializers import (
    AddInventorySerializer,
    ActivateInventorySerializer,
    InventoryTransactionSerializer,
    UnifiedEscrowTransactionSerializer,
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

    def get_product(self, variant_id):
        """Helper method to get product and check permissions"""
        variant = get_object_or_404(ProductVariant, id=variant_id)

        # Check if user is the seller or has appropriate permissions
        if (
            variant.product.seller != self.request.user
            and not self.request.user.is_staff
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You don't have permission to manage this product's inventory"
            )

        if not variant.product.is_active or not variant.is_active:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cannot modify inventory for inactive product")

        if not variant.product.status not in ["draft", "inactive", "sold"]:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"Cannot modify inventory for {variant.product.status} product"
            )

        return variant

    def get_product_escrow(self, variant_id):
        """Helper method to get product and check permissions"""
        variant = get_object_or_404(ProductVariant, id=variant_id)

        # Check if user is the seller or has appropriate permissions
        if variant.product.seller == self.request.user:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You don't have permission to initiated transaction for this product"
            )

        if not variant.product.is_active or not variant.is_active:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cannot modify inventory for inactive product")

        if not variant.product.status not in ["draft", "inactive", "sold"]:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"Cannot modify inventory for {variant.product.status} product"
            )

        return variant.product

    @action(
        detail=False,
        methods=["post"],
        url_path="add",
    )
    def add_inventory(self, request):
        """Add inventory to total"""
        variant_id = request.data.get("variant_id")
        if not variant_id:
            return self.error_response(
                message="variant_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        variant = self.get_product(variant_id)
        serializer = AddInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data["quantity"]
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.add_inventory(
                    variant=variant, quantity=quantity, user=request.user, notes=notes
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
        variant_id = request.data.get("variant_id")
        if not variant_id:
            return Response(
                {"error": "variant_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        variant = self.get_product(variant_id)
        serializer = ActivateInventorySerializer(data=request.data)

        if serializer.is_valid():
            quantity = serializer.validated_data.get("quantity")
            notes = serializer.validated_data.get("notes", "")

            with transaction.atomic():
                result = InventoryService.activate_inventory(
                    variant=variant, quantity=quantity, user=request.user, notes=notes
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
        url_path="create-transaction",
    )
    def create_escrow_transaction(self, request):
        """
        Unified endpoint for creating escrow transactions.
        Handles both direct purchases and negotiation-based purchases.
        """
        start_time = timezone.now()

        # Validate request data first
        serializer = UnifiedEscrowTransactionSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data
        variant_id = validated_data["variant_id"]
        quantity = validated_data["quantity"]
        notes = validated_data.get("notes", "")
        negotiation_id = validated_data.get("negotiation_id")  # Optional

        # Get the variant
        variant = get_object_or_404(
            ProductVariant.objects.select_related("product"), id=variant_id
        )

        try:
            # Determine transaction context (negotiation vs direct purchase)
            transaction_context = get_transaction_context(
                request.user, negotiation_id, variant
            )

            # Validate the transaction context
            validation_result = validate_transaction_context(
                request.user, transaction_context, quantity
            )
            if validation_result["error"]:
                return self.error_response(
                    message=validation_result["message"],
                    status_code=validation_result["status_code"],
                )

            # Create the escrow transaction
            with transaction.atomic():
                result = InventoryService.place_in_escrow(
                    variant=variant,
                    quantity=quantity,
                    buyer=request.user,
                    currency=variant.product.currency,
                    price=transaction_context["price"],  # Could be negotiated or None
                    notes=notes,
                )

                if not result:
                    return self.error_response(
                        message="Insufficient available inventory",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                variant_result, escrow_transaction, amount_paid = result

                # Update negotiation if applicable
                if transaction_context["negotiation"]:
                    link_negotiation_to_transaction(
                        transaction_context["negotiation"], escrow_transaction
                    )

                # Invalidate caches
                invalidate_caches(variant.product, transaction_context["negotiation"])

                # Prepare response data
                response_data = prepare_response_data(
                    variant_result,
                    escrow_transaction,
                    amount_paid,
                    quantity,
                    transaction_context,
                )

                duration = (timezone.now() - start_time).total_seconds() * 1000
                self.logger.info(
                    f"Escrow transaction created in {duration:.2f}ms "
                    f"(negotiation: {bool(negotiation_id)})"
                )

                return self.success_response(
                    data=response_data,
                    status_code=status.HTTP_201_CREATED,
                )

        except Exception as e:
            self.logger.error(f"Error creating escrow transaction: {str(e)}")
            return self.error_response(
                message=f"Failed to create transaction: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="status/(?P<variant_id>[^/.]+)")
    def inventory_status(self, request, variant_id=None):
        """Get current inventory status for a product"""
        variant = get_object_or_404(ProductVariant, id=variant_id)

        return self.success_response(
            data={
                "product_id": variant.product.id,
                "product_title": variant.product.title,
                "total": variant.product.total_inventory,
                "available": variant.product.available_inventory,
                "in_escrow": variant.product.in_escrow_inventory,
                "status": "active" if variant.is_active else "inactive",
            }
        )

    @action(detail=False, methods=["get"], url_path="history/(?P<variant_id>[^/.]+)")
    def inventory_history(self, request, variant_id=None):
        """Get inventory transaction history for a product"""
        variant = get_object_or_404(ProductVariant, id=variant_id)

        # Check permissions
        if variant.product.seller != request.user and not request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                "You don't have permission to view this product's inventory history"
            )

        transactions = (
            InventoryTransaction.objects.filter(variant=variant)
            .select_related("created_by")
            .order_by("-created_at")
        )

        serializer = self.get_serializer(transactions, many=True)
        return self.success_response(
            data={
                "product_id": variant.product.id,
                "product_title": variant.product.title,
                "transactions": serializer.data,
            }
        )

from rest_framework import permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.core.views import BaseViewSet
from apps.products.models import ProductImage, Product
from apps.products.serializers import (
    ProductImageListSerializer,
    ProductImageDetailSerializer,
    ProductImageWriteSerializer,
    ProductImageBulkCreateSerializer,
    ProductImageOrderUpdateSerializer,
)


class ProductImageViewSet(BaseViewSet):
    """
    API endpoint for managing product images.
    Supports CRUD operations, bulk creation, reordering, and primary image setting.
    """

    queryset = ProductImage.objects.all()
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["display_order", "created_at", "is_primary"]
    ordering = ["display_order", "-is_primary", "created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "list":
            return ProductImageListSerializer
        elif self.action in ["create", "update", "partial_update"]:
            return ProductImageWriteSerializer
        elif self.action == "bulk_create":
            return ProductImageBulkCreateSerializer
        elif self.action == "reorder":
            return ProductImageOrderUpdateSerializer
        return ProductImageDetailSerializer

    def get_permissions(self):
        """
        Custom permissions:
        - List/retrieve: Anyone can view product images
        - Create/update/delete: Only staff/admin users
        """
        if self.action in ["list", "retrieve", "by_product"]:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """
        Custom logic when creating a product image:
        - Handle primary status (unset other images as primary if needed)
        - Set display order if not provided
        """
        # Get the product
        product = serializer.validated_data.get("product")
        is_primary = serializer.validated_data.get("is_primary", False)

        # If display_order not provided, set it to be last in sequence
        if "display_order" not in serializer.validated_data:
            max_order = (
                ProductImage.objects.filter(product=product).aggregate(
                    max_order=Max("display_order")
                )["max_order"]
                or 0
            )
            serializer.validated_data["display_order"] = max_order + 1

        # Save the image
        instance = serializer.save()

        # If this image is primary, unset primary on other images
        if is_primary:
            ProductImage.objects.filter(product=product).exclude(pk=instance.pk).update(
                is_primary=False
            )

    def perform_update(self, serializer):
        """
        Custom logic when updating a product image:
        - Handle primary status (unset other images as primary if needed)
        """
        is_primary = serializer.validated_data.get("is_primary", False)
        instance = serializer.instance

        # Save the updated image
        updated_instance = serializer.save()

        # If this image is being set as primary, unset primary on other images
        if is_primary and not instance.is_primary:
            ProductImage.objects.filter(product=updated_instance.product).exclude(
                pk=updated_instance.pk
            ).update(is_primary=False)

    @extend_schema(
        request=ProductImageBulkCreateSerializer,
        responses={201: ProductImageListSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """
        Create multiple product images at once.
        """
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            instances = []
            for item in serializer.validated_data:
                product = item.get("product")
                is_primary = item.get("is_primary", False)

                # If display_order not provided, set it to be last in sequence
                if "display_order" not in item:
                    max_order = (
                        ProductImage.objects.filter(product=product).aggregate(
                            max_order=Max("display_order")
                        )["max_order"]
                        or 0
                    )
                    item["display_order"] = max_order + 1

                # Create the image
                instance = ProductImage.objects.create(**item)
                instances.append(instance)

                # If this image is primary, unset primary on other images
                if is_primary:
                    ProductImage.objects.filter(product=product).exclude(
                        pk=instance.pk
                    ).update(is_primary=False)

        # Return the created instances
        result_serializer = ProductImageListSerializer(
            instances, many=True, context={"request": request}
        )
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ProductImageOrderUpdateSerializer,
        responses={200: {"description": "Images reordered successfully"}},
    )
    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """
        Update the display order of multiple images.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Images reordered successfully"}, status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["get"])
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="product_id",
                description="Filter by product ID",
                required=True,
                type=int,
            )
        ]
    )
    def by_product(self, request):
        """
        Get all images for a specific product.
        """
        product_id = request.query_params.get("product_id")
        if not product_id:
            return Response(
                {"error": "product_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = get_object_or_404(Product, pk=product_id)
        images = ProductImage.objects.filter(product=product).order_by(
            "display_order", "-is_primary"
        )

        serializer = ProductImageListSerializer(
            images, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def set_primary(self, request, pk=None):
        """
        Set this image as the primary image for its product.
        """
        image = self.get_object()

        with transaction.atomic():
            # Unset primary on all other images for this product
            ProductImage.objects.filter(product=image.product).update(is_primary=False)

            # Set this image as primary
            image.is_primary = True
            image.save()

        serializer = self.get_serializer(image)
        return Response(serializer.data)

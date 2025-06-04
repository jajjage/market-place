import logging
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from apps.products.product_base.models import Product
from .services import BreadcrumbService
from .serializers import (
    BreadcrumbSerializer,
    BreadcrumbBulkCreateSerializer,
    BreadcrumbCreateSerializer,
)

logger = logging.getLogger("breadcrumbs_performance")


class BreadcrumbRateThrottle(UserRateThrottle):
    scope = "breadcrumb"


class BreadcrumbAnonRateThrottle(AnonRateThrottle):
    scope = "breadcrumb_anon"


# GET /api/products/{product_id}/breadcrumbs/
@api_view(["GET"])
@throttle_classes([BreadcrumbRateThrottle, BreadcrumbAnonRateThrottle])
def get_product_breadcrumbs(request, product_id):
    """Get breadcrumbs for a specific product"""
    try:
        # Verify product exists
        get_object_or_404(Product, id=product_id)

        breadcrumbs = BreadcrumbService.get_product_breadcrumbs(product_id)
        return Response(
            {"success": True, "data": breadcrumbs, "count": len(breadcrumbs)}
        )

    except Exception as e:
        logger.error(f"Error getting breadcrumbs for product {product_id}: {str(e)}")
        return Response(
            {"success": False, "error": "Failed to retrieve breadcrumbs"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# POST /api/products/{product_id}/breadcrumbs/bulk/
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BreadcrumbRateThrottle])
def bulk_create_breadcrumbs(request, product_id):
    """Bulk create/update breadcrumbs for a product (Admin only)"""
    if not request.user.is_staff:
        return Response(
            {"success": False, "error": "Admin access required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        product = get_object_or_404(Product, id=product_id)

        serializer = BreadcrumbBulkCreateSerializer(
            data=request.data, context={"product_id": product_id}
        )

        if serializer.is_valid():
            breadcrumbs = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": f"Created {len(breadcrumbs)} breadcrumbs",
                    "data": BreadcrumbSerializer(breadcrumbs, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(
            f"Error bulk creating breadcrumbs for product {product_id}: {str(e)}"
        )
        return Response(
            {"success": False, "error": "Failed to create breadcrumbs"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# POST /api/products/{product_id}/breadcrumbs/default/
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BreadcrumbRateThrottle])
def create_default_breadcrumbs(request, product_id):
    """Create default breadcrumbs based on product category (Admin only)"""
    if not request.user.is_staff:
        return Response(
            {"success": False, "error": "Admin access required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        product = get_object_or_404(Product, id=product_id)
        breadcrumbs = BreadcrumbService.create_default_breadcrumbs(product)

        return Response(
            {
                "success": True,
                "message": f"Created {len(breadcrumbs)} default breadcrumbs",
                "data": BreadcrumbSerializer(breadcrumbs, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(
            f"Error creating default breadcrumbs for product {product_id}: {str(e)}"
        )
        return Response(
            {"success": False, "error": "Failed to create default breadcrumbs"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# PUT /api/breadcrumbs/{breadcrumb_id}/
@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BreadcrumbRateThrottle])
def update_breadcrumb(request, breadcrumb_id):
    """Update a specific breadcrumb (Admin only)"""
    if not request.user.is_staff:
        return Response(
            {"success": False, "error": "Admin access required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        serializer = BreadcrumbCreateSerializer(data=request.data)
        if serializer.is_valid():
            breadcrumb = BreadcrumbService.update_breadcrumb(
                breadcrumb_id, serializer.validated_data
            )
            return Response(
                {"success": True, "data": BreadcrumbSerializer(breadcrumb).data}
            )

        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(f"Error updating breadcrumb {breadcrumb_id}: {str(e)}")
        return Response(
            {"success": False, "error": "Failed to update breadcrumb"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# DELETE /api/breadcrumbs/{breadcrumb_id}/
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([BreadcrumbRateThrottle])
def delete_breadcrumb(request, breadcrumb_id):
    """Delete a specific breadcrumb (Admin only)"""
    if not request.user.is_staff:
        return Response(
            {"success": False, "error": "Admin access required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        BreadcrumbService.delete_breadcrumb(breadcrumb_id)
        return Response({"success": True, "message": "Breadcrumb deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting breadcrumb {breadcrumb_id}: {str(e)}")
        return Response(
            {"success": False, "error": "Failed to delete breadcrumb"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

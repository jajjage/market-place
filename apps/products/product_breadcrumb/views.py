import logging
from rest_framework import status, permissions, viewsets, mixins
from rest_framework.decorators import action  # For custom actions if needed
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import (
    ContentType,
)  # Needed for GenericForeignKey context

from apps.products.product_breadcrumb.utils.rate_limiting import (
    BreadcrumbRateThrottle,
)  # Your rate limiter
from .services import BreadcrumbService
from .models import Breadcrumb  # Import the Breadcrumb model directly

from .serializers import (
    BreadcrumbSerializer,
    BreadcrumbBulkCreateSerializer,
    # BreadcrumbCreateSerializer is used internally by BulkCreate and Update
)

logger = logging.getLogger("breadcrumbs_performance")


# Assuming you have a BaseViewSet, inherit from it
# For demonstration, I'll use mixins.RetrieveModelMixin, etc.
# Replace with your actual BaseViewSet if it provides permissions/throttling.
class BreadcrumbViewSet(
    mixins.RetrieveModelMixin,  # For GET /api/breadcrumbs/{id}/
    mixins.UpdateModelMixin,  # For PUT/PATCH /api/breadcrumbs/{id}/
    mixins.DestroyModelMixin,  # For DELETE /api/breadcrumbs/{id}/
    viewsets.GenericViewSet,  # Provides the base for ViewSets
):
    queryset = Breadcrumb.objects.all()
    serializer_class = BreadcrumbSerializer
    permission_classes = [
        permissions.IsAuthenticated
    ]  # Or your custom permission class
    throttle_classes = [BreadcrumbRateThrottle]

    def get_serializer_context(self):
        """Pass request context to serializers."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # --- Replaces update_breadcrumb function ---
    def update(self, request, *args, **kwargs):
        """Update a specific breadcrumb (Admin only)"""
        if not request.user.is_staff:
            return Response(
                {"success": False, "error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            instance = self.get_object()  # Gets the Breadcrumb instance
            serializer = self.get_serializer(
                instance, data=request.data, partial=True
            )  # partial=True for PATCH
            serializer.is_valid(raise_exception=True)

            # Call the service method, passing the breadcrumb ID and validated data
            updated_breadcrumb = BreadcrumbService.update_breadcrumb(
                instance.id, serializer.validated_data
            )
            # You might return the updated instance directly, or the service's return.
            # Using the instance and re-serializing it ensures consistency with ModelViewSet behavior.
            return Response(self.get_serializer(updated_breadcrumb).data)

        except Exception as e:
            logger.error(f"Error updating breadcrumb {kwargs.get('pk')}: {str(e)}")
            return Response(
                {"success": False, "error": "Failed to update breadcrumb"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # --- Replaces delete_breadcrumb function ---
    def destroy(self, request, *args, **kwargs):
        """Delete a specific breadcrumb (Admin only)"""
        if not request.user.is_staff:
            return Response(
                {"success": False, "error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            instance = self.get_object()  # Gets the Breadcrumb instance
            BreadcrumbService.delete_breadcrumb(instance.id)  # Call service method
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting breadcrumb {kwargs.get('pk')}: {str(e)}")
            return Response(
                {"success": False, "error": "Failed to delete breadcrumb"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # --- Custom action to replace bulk_create_breadcrumbs (POST /api/breadcrumbs/{obj_type}/{obj_id}/bulk/) ---
    # This action allows creating breadcrumbs for a specific object via its ID.
    @action(
        detail=False,
        methods=["post"],
        url_path=r"(?P<app_label>[-\w]+)/(?P<model_name>[-\w]+)/(?P<obj_id>\d+)/bulk",
    )
    def bulk_create_for_object(self, request, app_label, model_name, obj_id):
        """
        Bulk create/update breadcrumbs for a specific object (e.g., product, transaction). Admin only.
        URL example: /api/breadcrumbs/products/product/1/bulk/
                     /api/breadcrumbs/transactions/transaction/123/bulk/
        """
        if not request.user.is_staff:
            return Response(
                {"success": False, "error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            # Get the ContentType and the actual object instance
            content_type = get_object_or_404(
                ContentType, app_label=app_label, model=model_name
            )
            obj = content_type.get_object_for_this_type(pk=obj_id)

            # Pass the object instance to the serializer context
            serializer = BreadcrumbBulkCreateSerializer(
                data=request.data, context={"content_object": obj}
            )

            if serializer.is_valid(raise_exception=True):
                breadcrumbs = (
                    serializer.save()
                )  # This calls BreadcrumbService.bulk_create_breadcrumbs
                return Response(
                    {
                        "success": True,
                        "message": f"Created {len(breadcrumbs)} breadcrumbs for {model_name} ID {obj_id}",
                        "data": BreadcrumbSerializer(breadcrumbs, many=True).data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            # The raise_exception=True handles 400 for invalid data automatically

        except ContentType.DoesNotExist:
            return Response(
                {"success": False, "error": "Invalid content type specified."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                f"Error bulk creating breadcrumbs for {model_name} ID {obj_id}: {str(e)}"
            )
            return Response(
                {"success": False, "error": "Failed to create breadcrumbs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # --- Custom action to replace create_default_breadcrumbs (POST /api/breadcrumbs/{obj_type}/{obj_id}/default/) ---
    @action(
        detail=False,
        methods=["post"],
        url_path=r"(?P<app_label>[-\w]+)/(?P<model_name>[-\w]+)/(?P<obj_id>\d+)/default",
    )
    def create_default_for_object(self, request, app_label, model_name, obj_id):
        """
        Create default breadcrumbs based on object type/category (Admin only).
        This method needs conditional logic based on the 'model_name'.
        """
        if not request.user.is_staff:
            return Response(
                {"success": False, "error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            content_type = get_object_or_404(
                ContentType, app_label=app_label, model=model_name
            )
            obj = content_type.get_object_for_this_type(pk=obj_id)

            breadcrumbs = []
            if (
                model_name == "product"
            ):  # Assuming 'product' is the actual model name string
                breadcrumbs = BreadcrumbService.generate_breadcrumbs_for_product(obj)
            elif (
                model_name == "transaction"
            ):  # Assuming 'transaction' is the actual model name string
                breadcrumbs = BreadcrumbService.generate_breadcrumbs_for_transaction(
                    obj
                )
            elif (
                model_name == "dispute"
            ):  # Assuming 'dispute' is the actual model name string
                breadcrumbs = BreadcrumbService.generate_breadcrumbs_for_dispute(obj)
            elif (
                model_name == "user"
            ):  # Assuming 'user' is the actual model name string (or 'profile')
                breadcrumbs = BreadcrumbService.generate_breadcrumbs_for_user_profile(
                    obj
                )
            else:
                return Response(
                    {
                        "success": False,
                        "error": f"Default breadcrumb generation not supported for model '{model_name}'.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "success": True,
                    "message": f"Created {len(breadcrumbs)} default breadcrumbs for {model_name} ID {obj_id}",
                    "data": BreadcrumbSerializer(breadcrumbs, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )

        except ContentType.DoesNotExist:
            return Response(
                {"success": False, "error": "Invalid content type specified."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                f"Error creating default breadcrumbs for {model_name} ID {obj_id}: {str(e)}"
            )
            return Response(
                {"success": False, "error": "Failed to create default breadcrumbs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

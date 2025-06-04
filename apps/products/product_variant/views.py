from rest_framework import status
from django.core.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from apps.core.views import BaseViewSet
from .models import ProductVariant, ProductVariantType
from .serializers import (
    ProductVariantSerializer,
    ProductVariantTypeSerializer,
)
from .services import ProductVariantService, CACHE_TTL

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page


class ProductVariantTypeViewSet(BaseViewSet):
    queryset = ProductVariantType.objects.all()
    serializer_class = ProductVariantTypeSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    @method_decorator(cache_page(CACHE_TTL))
    def list(self, request, *args, **kwargs):
        variant_types = ProductVariantService.get_variant_types()
        serializer = self.get_serializer(variant_types, many=True)
        return self.success_response(
            data=serializer.data,
            message="Product variant types retrieved successfully",
        )


class ProductVariantViewSet(BaseViewSet):
    serializer_class = ProductVariantSerializer

    def get_queryset(self):
        product_id = self.request.query_params.get("product_id")
        if product_id:
            return ProductVariantService.get_product_variants(int(product_id))
        return ProductVariant.objects.none()

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
            "generate_combinations",
        ]:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    @method_decorator(cache_page(CACHE_TTL))
    def matrix(self, request):
        """Get variant matrix for a product."""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            matrix = ProductVariantService.get_variant_matrix(int(product_id))
            variant_types = ProductVariantService.get_variant_types()

            return Response(
                {
                    "variant_types": ProductVariantTypeSerializer(
                        variant_types, many=True
                    ).data,
                    "variants": matrix,
                }
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create variants synchronously or asynchronously."""
        if not request.user.is_staff:
            return Response(
                {"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN
            )

        product_id = request.data.get("product_id")
        variant_data = request.data.get("variants", [])

        if not product_id or not isinstance(variant_data, list) or not variant_data:
            return Response(
                {"error": "product_id and variants list are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # If the client included “async”: true, enqueue background task:
            if request.data.get("async", False):
                async_res = ProductVariantService.bulk_create_variants_async(
                    {
                        "product_id": int(product_id),
                        "variant_combinations": variant_data,
                    }
                )
                return Response(
                    {
                        "message": "Bulk creation queued",
                        "task_id": async_res.id,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            # Otherwise, create synchronously via service:
            created_variants = ProductVariantService.bulk_create_variants(
                int(product_id), variant_data
            )
            serializer = ProductVariantSerializer(created_variants, many=True)
            return Response(
                {
                    "message": f"Successfully created {len(created_variants)} variants",
                    "variants": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"])
    def generate_combinations(self, request):
        """Generate all possible variant combinations, then create & update cache."""
        if not request.user.is_staff:
            return self.error_response(
                message="Admin access required", status_code=status.HTTP_403_FORBIDDEN
            )

        product_id = request.data.get("product_id")
        variant_type_options = request.data.get("variant_type_options", {})
        base_price = request.data.get("base_price", None)

        if not product_id or not isinstance(variant_type_options, dict):
            return self.error_response(
                message="product_id and variant_type_options (as dict) are required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Convert variant_type_options keys to ints if they came in as strings:
            variant_type_options = {int(k): v for k, v in variant_type_options.items()}

            # Enqueue background task:
            async_res = ProductVariantService.generate_combinations_async(
                int(product_id), variant_type_options, base_price
            )
            return Response(
                {
                    "message": "Generation + creation queued",
                    "task_id": async_res.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except ValueError:
            return self.error_response(
                message="variant_type_options keys must be integers",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"])
    def variant_template(self, request):
        """Get variant template for product creation/edit forms."""
        variant_type_ids = request.query_params.getlist("variant_types")
        if not variant_type_ids:
            return self.error_response(
                message="variant_types parameter is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            variant_type_ids = [int(pk) for pk in variant_type_ids]
            template = ProductVariantService.get_variant_template_for_product(
                variant_type_ids
            )
            return Response(template)
        except ValueError:
            return self.error_response(
                message="Invalid variant_type IDs",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

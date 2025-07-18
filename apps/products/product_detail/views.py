from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404

from apps.core.views import BaseViewSet

from .models import ProductDetail, ProductDetailTemplate
from .serializers import (
    ProductDetailFromTemplateSerializer,
    ProductDetailSerializer,
    ProductDetailSummarySerializer,
    ProductDetailGroupedSerializer,
    ProductDetailTemplateSerializer,
    ProductDetailTemplateCreateSerializer,
    ProductDetailTemplateUpdateSerializer,
    ProductDetailTemplateSummarySerializer,
    ProductDetailTemplateBulkCreateSerializer,
    ProductDetailTemplateUsageSerializer,
    ProductDetailBulkCreateSerializer,
)
from .services import ProductDetailService


class ProductDetailViewSet(BaseViewSet):
    """ViewSet for ProductDetail with caching and rate limiting"""

    serializer_class = ProductDetailSerializer
    lookup_field = "id"

    def get_throttles(self):
        """Apply custom throttles for list, retrieve, create, update, and partial_update actions."""
        from apps.products.product_detail.utils.rate_limiting import (
            ProductDetailListThrottle,
            ProductDetailRetrieveThrottle,
            ProductDetailWriteThrottle,
        )

        action = self.action if hasattr(self, "action") else None
        if action == "list":
            return [ProductDetailListThrottle()]
        elif action == "retrieve":
            return [ProductDetailRetrieveThrottle()]
        elif action in [
            "create",
            "update",
            "partial_update",
            "create_from_template",
            "bulk_create_from_templates",
        ]:
            return [ProductDetailWriteThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        product_id = self.kwargs.get("product_pk")
        if product_id:
            return ProductDetail.objects.filter(
                product_id=product_id, is_active=True
            ).select_related("product", "template")
        return ProductDetail.objects.select_related("product", "template")

    def list(self, request, *args, **kwargs):
        """List product details with optional filtering"""
        product_id = self.kwargs.get("product_pk")
        detail_type = request.query_params.get("type")
        highlighted = request.query_params.get("highlighted") == "true"

        if not product_id:
            return self.error_response(
                message="Product ID is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        details = ProductDetailService.get_product_details(
            product_id=product_id, detail_type=detail_type, highlighted_only=highlighted
        )

        serializer = self.get_serializer(details, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["get"])
    def grouped(self, request, *args, **kwargs):
        """Get details grouped by type"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        grouped_details = ProductDetailService.get_grouped_details(product_id)
        grouped_list = [
            (detail_type, details) for detail_type, details in grouped_details.items()
        ]

        serializer = ProductDetailGroupedSerializer(grouped_list, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["get"])
    def available_templates(self, request, *args, **kwargs):
        """Get available templates for this product's category"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return Response(
                {"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        from apps.products.product_base.models import Product

        product = get_object_or_404(Product, id=product_id)
        category = getattr(product, "category", None)

        # Get available templates for this product's category
        templates = ProductDetailService.get_templates_for_category(category.id)

        # Exclude templates already used for this product
        used_template_ids = ProductDetail.objects.filter(
            product=product, template__isnull=False
        ).values_list("template_id", flat=True)

        # Support both QuerySet and list return types
        if hasattr(templates, "exclude"):
            available_templates = templates.exclude(id__in=used_template_ids)
        else:
            used_template_ids_set = set(used_template_ids)
            available_templates = [
                t for t in templates if t.id not in used_template_ids_set
            ]

        from .serializers import ProductDetailTemplateSerializer

        serializer = ProductDetailTemplateSerializer(available_templates, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["post"])
    def create_from_template(self, request, *args, **kwargs):
        """Create a product detail from a template"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return self.error_response(
                message="Product ID is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        from apps.products.product_base.models import Product

        product = get_object_or_404(Product, id=product_id)

        serializer = ProductDetailFromTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template_id = serializer.validated_data["template_id"]
            value = serializer.validated_data["value"]

            template = get_object_or_404(ProductDetailTemplate, id=template_id)

            # Check if template is already used for this product
            if ProductDetail.objects.filter(
                product=product, template=template
            ).exists():
                return self.error_response(
                    message="This template has already been used for this product",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Create detail from template
            detail = ProductDetailService.create_from_template(
                product=product,
                template=template,
                value=value,
                **serializer.validated_data.get("extra_fields", {})
            )

            response_serializer = ProductDetailSerializer(detail)
            return self.success_response(
                data=response_serializer.data, status_code=status.HTTP_201_CREATED
            )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=["get"])
    def highlighted(self, request, *args, **kwargs):
        """Get only highlighted details"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return self.error_reponse(
                message="Product ID is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        details = ProductDetailService.get_highlighted_details(product_id)
        serializer = ProductDetailSummarySerializer(details, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request, *args, **kwargs):
        """Bulk create product details"""
        product_id = self.kwargs.get("product_pk")

        if not product_id:
            return self.error_response(
                message="Product ID is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        from apps.products.product_base.models import Product

        product = get_object_or_404(Product, id=product_id)

        serializer = ProductDetailBulkCreateSerializer(data=request.data)
        if serializer.is_valid():
            details = ProductDetailService.bulk_create_details(
                product=product, details_data=serializer.validated_data["details"]
            )

            response_serializer = ProductDetailSerializer(details, many=True)
            return self.success_response(
                data=response_serializer.data, status_code=status.HTTP_201_CREATED
            )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )


class ProductDetailTemplateViewSet(BaseViewSet):
    """ViewSet for ProductDetail templates (admin-created)"""

    queryset = ProductDetailTemplate.objects.all()
    serializer_class = ProductDetailTemplateSerializer

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return ProductDetailTemplateCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return ProductDetailTemplateUpdateSerializer
        elif self.action == "list":
            return ProductDetailTemplateSummarySerializer
        elif self.action == "bulk_create":
            return ProductDetailTemplateBulkCreateSerializer
        return ProductDetailTemplateSerializer

    def get_permissions(self):
        """
        Only allow admins to create/update/delete templates
        Anyone can view templates
        """
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = []
        return [permission() for permission in permission_classes]

    def get_throttles(self):
        """Apply rate limiting for write operations"""
        from apps.products.product_detail.utils.rate_limiting import (
            ProductDetailWriteThrottle,
        )

        if self.action in ["create", "update", "partial_update"]:
            return [ProductDetailWriteThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                template = ProductDetailService.create_template(
                    serializer.validated_data
                )
                response_serializer = self.get_serializer(template)
                return self.success_response(
                    data=response_serializer.data, status_code=status.HTTP_201_CREATED
                )
            except ValueError as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )
        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.get("partial", False)
        )
        if serializer.is_valid():
            try:
                template = ProductDetailService.update_template(
                    instance.id, **serializer.validated_data
                )
                response_serializer = self.get_serializer(template)
                return self.success_response(data=response_serializer.data)
            except ValueError as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )
        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            success = ProductDetailService.delete_template(instance.id)
            if success:
                return self.success_response(status_code=status.HTTP_204_NO_CONTENT)
            else:
                return self.error_response(
                    message="Cannot delete template that is in use",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def for_category(self, request):
        """Get templates available for a specific category"""
        category_id = request.query_params.get("category_id")
        if not category_id:
            return self.error_response(
                message="category_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        templates = ProductDetailService.get_templates_for_category(
            category_id=category_id if category_id else None
        )

        serializer = ProductDetailTemplateSummarySerializer(templates, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[IsAdminUser])
    def bulk_create(self, request):
        """Bulk create templates"""
        serializer = ProductDetailTemplateBulkCreateSerializer(data=request.data)

        if serializer.is_valid():
            try:
                templates = ProductDetailService.bulk_create_templates(
                    serializer.validated_data["templates"]
                )
                response_serializer = ProductDetailTemplateSerializer(
                    templates, many=True
                )
                return self.success_response(
                    data=response_serializer.data, status_code=status.HTTP_201_CREATED
                )
            except ValueError as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )

        return self.error_response(
            data=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=["get"])
    def usage(self, request, pk=None):
        """Get usage information for a template"""
        try:
            usage_info = ProductDetailService.validate_template_usage(pk)
            serializer = ProductDetailTemplateUsageSerializer(usage_info)
            return self.success_response(data=serializer.data)
        except ProductDetailTemplate.DoesNotExist:
            return self.error_response(
                message="Template not found", status_code=status.HTTP_404_NOT_FOUND
            )

from rest_framework import status
from django.core.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db import models
from django.db.models import Prefetch


from apps.core.views import BaseViewSet
from .models import ProductVariant, ProductVariantType, ProductVariantOption
from .serializers import (
    ProductVariantSerializer,
    ProductVariantTypeSerializer,
    ProductVariantOptionSerializer,
    ProductVariantCreateSerializer,
    ProductVariantBulkCreateSerializer,
    ProductVariantStockUpdateSerializer,
    ProductVariantCombinationGeneratorSerializer,
    ProductVariantMatrixSerializer,
    ProductVariantStatsSerializer,
    ProductVariantTypeBulkCreateSerializer,
    ProductVariantOptionBulkCreateSerializer,
)
from .services import ProductVariantService, CACHE_TTL


class ProductVariantTypeViewSet(BaseViewSet):
    """ViewSet for managing product variant types"""

    queryset = ProductVariantType.objects.all()
    serializer_class = ProductVariantTypeSerializer

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
        ]:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "bulk_create":
            return ProductVariantTypeBulkCreateSerializer
        return ProductVariantTypeSerializer

    def get_queryset(self):
        """Optimize queryset with annotations"""
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = queryset.annotate(
                option_count=models.Count(
                    "options", filter=models.Q(options__is_active=True), distinct=True
                )
            ).prefetch_related(
                models.Prefetch(
                    "options",
                    queryset=ProductVariantOption.objects.filter(
                        is_active=True
                    ).select_related("variant_type"),
                )
            )
        return queryset

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create variant types"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            created_types = ProductVariantService.bulk_create_variant_types(
                serializer.validated_data["types"]
            )
            response_serializer = ProductVariantTypeSerializer(created_types, many=True)
            return self.success_response(
                data=response_serializer.data,
                message=f"Successfully created {len(created_types)} variant types",
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @method_decorator(cache_page(CACHE_TTL))
    def list(self, request, *args, **kwargs):
        """Get all variant types with options"""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return self.success_response(
                data=serializer.data,
                message="Product variant types retrieved successfully",
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        """Create a new variant type"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            variant_type = serializer.save()
            return self.success_response(
                data=serializer.data,
                message=f"Variant type '{variant_type.name}' created successfully",
                status_code=status.HTTP_201_CREATED,
            )
        return self.error_response(
            message=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ProductVariantOptionViewSet(BaseViewSet):
    """ViewSet for managing variant options"""

    queryset = ProductVariantOption.objects.all()
    serializer_class = ProductVariantOptionSerializer

    def get_queryset(self):
        """Filter options by variant type if provided with optimized queries"""
        queryset = super().get_queryset()

        # Always apply select_related for variant_type to avoid N+1 queries
        queryset = queryset.select_related("variant_type")

        # For list action, optimize further with field selection and caching
        if self.action == "list":
            # Cache key based on variant_type_id if provided
            variant_type_id = self.request.query_params.get("variant_type")
            if variant_type_id:
                queryset = queryset.filter(variant_type_id=variant_type_id)

            # Optimize field selection
            queryset = queryset.only(
                "id",
                "value",
                "slug",
                "sort_order",
                "display_value",
                "color_code",
                "price_adjustment",
                "is_active",
                "variant_type__id",
                "variant_type__name",
            ).order_by("sort_order")

            # Use prefetch_related for any potential reverse relationships
            queryset = queryset.prefetch_related(
                models.Prefetch(
                    "variant_type__options",
                    queryset=ProductVariantOption.objects.filter(is_active=True),
                    to_attr="active_options",
                )
            )

        return queryset

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
        ]:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "bulk_create":
            return ProductVariantOptionBulkCreateSerializer
        return ProductVariantOptionSerializer

    @method_decorator(cache_page(CACHE_TTL))
    def list(self, request, *args, **kwargs):
        """Get all options with caching"""
        variant_type_id = request.query_params.get("variant_type")

        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create variant options"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            created_options = ProductVariantService.bulk_create_variant_options(
                variant_type_id=serializer.validated_data["variant_type_id"],
                options_data=serializer.validated_data["options"],
            )
            response_serializer = ProductVariantOptionSerializer(
                created_options, many=True
            )
            return self.success_response(
                data=response_serializer.data,
                message=f"Successfully created {len(created_options)} variant options",
                status_code=status.HTTP_201_CREATED,
            )
        except ProductVariantType.DoesNotExist:
            return self.error_response(
                message="Variant type not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProductVariantViewSet(BaseViewSet):
    """Enhanced ViewSet for managing product variants"""

    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get variants with various filtering options and optimized queries"""
        product_id = self.request.query_params.get("product_id")
        if not product_id:
            return ProductVariant.objects.none()

        # Determine which fields to fetch based on action
        fields_subset = {
            "id",
            "sku",
            "price",
            "stock_quantity",
            "reserved_quantity",
            "low_stock_threshold",
            "is_active",
        }

        if self.action == "list":
            # Add fields needed for list view
            fields_subset.update({"total_inventory", "in_escrow_inventory"})
        elif self.action in ["retrieve", "update"]:
            # Add additional fields for detail view
            fields_subset.update(
                {
                    "cost_price",
                    "weight",
                    "dimensions_length",
                    "dimensions_width",
                    "dimensions_height",
                    "is_digital",
                    "is_backorderable",
                    "expected_restock_date",
                }
            )

        active_only = (
            self.request.query_params.get("active_only", "true").lower() == "true"
        )
        in_stock_only = (
            self.request.query_params.get("in_stock_only", "false").lower() == "true"
        )

        return ProductVariantService.get_product_variants(
            product_id=product_id,
            active_only=active_only,
            in_stock_only=in_stock_only,
            with_options=True,
            with_images=self.action in ["retrieve", "update"],
            fields_subset=fields_subset,
        )

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return ProductVariantCreateSerializer
        elif self.action == "bulk_create":
            return ProductVariantBulkCreateSerializer
        elif self.action == "generate_combinations":
            return ProductVariantCombinationGeneratorSerializer
        elif self.action == "bulk_update_stock":
            return ProductVariantStockUpdateSerializer
        return ProductVariantSerializer

    # def get_permissions(self):
    #     """Define permissions for different actions"""
    #     admin_actions = [
    #         "create",
    #         "update",
    #         "partial_update",
    #         "destroy",
    #         "bulk_create",
    #         "generate_combinations",
    #         "bulk_update_stock",
    #         "validate_combination",
    #     ]
    #     if self.action in admin_actions:
    #         return [IsAdminUser()]
    #     return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        """List variants with enhanced filtering"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id parameter is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            variants = self.get_queryset()
            serializer = self.get_serializer(variants, many=True)
            return self.success_response(
                data=serializer.data,
                message=f"Retrieved {len(variants)} variants",
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        """Create a single variant"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                variant = serializer.save()
                response_serializer = ProductVariantSerializer(variant)
                return self.success_response(
                    data=response_serializer.data,
                    message=f"Variant '{variant.sku}' created successfully",
                    status_code=status.HTTP_201_CREATED,
                )
            except ValidationError as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )
        return self.error_response(
            message=f"Validation failed {serializer.errors}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["get"])
    @method_decorator(cache_page(CACHE_TTL))
    def matrix(self, request):
        """Get variant matrix for a product with enhanced data and optimized queries"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Get variant matrix and types in parallel using asyncio or Promise.all
            matrix = ProductVariantService.get_variant_matrix(int(product_id))

            # Get only the variant types that are actually used in the matrix
            used_type_ids = {
                option["type_id"]
                for variant_data in matrix.values()
                for option in variant_data.get("options", [])
            }

            # Fetch only the relevant variant types with optimized query
            variant_types = (
                ProductVariantType.objects.filter(id__in=used_type_ids, is_active=True)
                .prefetch_related(
                    Prefetch(
                        "options",
                        queryset=ProductVariantOption.objects.filter(is_active=True)
                        .only(
                            "id",
                            "value",
                            "display_value",
                            "slug",
                            "sort_order",
                            "variant_type_id",
                        )
                        .order_by("sort_order"),
                    )
                )
                .order_by("sort_order")
            )

            serializer = ProductVariantMatrixSerializer(
                {"variant_types": variant_types, "variants": matrix}
            )

            return Response(serializer.data)

        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Enhanced bulk create with better validation and async support"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data
        product_id = validated_data["product_id"]
        variant_data = validated_data["variants"]
        is_async = validated_data.get("async", False)

        try:
            if is_async:
                # Queue background task
                async_result = ProductVariantService.create_variants_async(
                    product_id=product_id, variant_combinations=variant_data
                )
                return Response(
                    {
                        "message": "Bulk creation queued successfully",
                        "task_id": async_result.id,
                        "estimated_variants": len(variant_data),
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                # Create synchronously
                created_variants = ProductVariantService.bulk_create_variants(
                    product_id=product_id,
                    variant_data=variant_data,
                    validate_uniqueness=True,
                    update_cache=True,
                )

                response_serializer = ProductVariantSerializer(
                    created_variants, many=True
                )
                return self.success_response(
                    data=response_serializer.data,
                    message=f"Successfully created {len(created_variants)} variants",
                    status_code=status.HTTP_201_CREATED,
                )

        except ValidationError as e:
            return self.error_response(
                message="Validation error",
                errors=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"])
    def generate_combinations(self, request):
        """Generate and create all possible variant combinations"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data

        try:
            # Always run async for combination generation due to potential size
            async_result = ProductVariantService.generate_and_create_variants_async(
                product_id=validated_data["product_id"],
                variant_type_options=validated_data["variant_type_options"],
                base_price=validated_data.get("base_price"),
                sku_separator=validated_data.get("sku_separator", "-"),
            )

            # Get estimated combinations for user feedback
            template = ProductVariantService.get_variant_template_for_product(
                list(validated_data["variant_type_options"].keys())
            )

            return Response(
                {
                    "message": "Variant generation queued successfully",
                    "task_id": async_result.id,
                    "estimated_combinations": template["total_combinations"],
                    "estimated_storage_mb": template["estimated_storage_mb"],
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"])
    def variant_template(self, request):
        """Get variant template for product creation forms"""
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
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"])
    def validate_combination(self, request):
        """Validate a variant combination"""
        product_id = request.data.get("product_id")
        option_ids = request.data.get("option_ids", [])

        if not product_id or not option_ids:
            return self.error_response(
                message="product_id and option_ids are required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validation_result = ProductVariantService.validate_variant_combination(
                product_id=int(product_id), option_ids=option_ids
            )
            return Response(validation_result)
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"])
    def bulk_update_stock(self, request):
        """Bulk update stock quantities"""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Validation failed",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            is_async = serializer.validated_data.get("async", False)
            stock_updates = serializer.validated_data["stock_updates"]

            if is_async:
                async_result = ProductVariantService.bulk_stock_update_async(
                    stock_updates
                )
                return Response(
                    {
                        "message": "Stock update queued successfully",
                        "task_id": async_result.id,
                        "update_count": len(stock_updates),
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                results = ProductVariantService.bulk_update_stock(stock_updates)
                return Response(
                    {
                        "message": "Stock updates completed",
                        "success_count": len(results["success"]),
                        "error_count": len(results["errors"]),
                        "results": results,
                    }
                )

        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get variant statistics for a product"""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stats = ProductVariantService.get_variant_stats(int(product_id))
            serializer = ProductVariantStatsSerializer(stats)
            return Response(serializer.data)
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"])
    def reserve_stock(self, request, pk=None):
        """Reserve stock for a variant"""
        quantity = request.data.get("quantity")
        if not quantity or quantity <= 0:
            return self.error_response(
                message="Valid quantity is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            success = ProductVariantService.reserve_stock(int(pk), int(quantity))
            if success:
                return Response(
                    {
                        "message": f"Successfully reserved {quantity} units",
                        "variant_id": pk,
                        "reserved_quantity": quantity,
                    }
                )
            else:
                return self.error_response(
                    message="Insufficient stock available",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"])
    def release_stock(self, request, pk=None):
        """Release reserved stock for a variant"""
        quantity = request.data.get("quantity")
        if not quantity or quantity <= 0:
            return self.error_response(
                message="Valid quantity is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            success = ProductVariantService.release_stock(int(pk), int(quantity))
            if success:
                return Response(
                    {
                        "message": f"Successfully released {quantity} units",
                        "variant_id": pk,
                        "released_quantity": quantity,
                    }
                )
            else:
                return self.error_response(
                    message="Variant not found", status_code=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

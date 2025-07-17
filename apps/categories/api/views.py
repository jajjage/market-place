import logging
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema

from rest_framework.exceptions import ValidationError

from apps.categories.documents import CategoryDocument
from apps.core.views import BaseResponseMixin, BaseViewSet


from ..throttle import CategoryRateThrottle

from apps.core.utils.cache_key_manager import CacheKeyManager
from ..models import Category
from ..services import CategoryService
from .serializers import (
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryWriteSerializer,
    CategoryTreeSerializer,
)
from .schema import category_viewset_schema
from elasticsearch.dsl import Q
from django.db.models import Count, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


@extend_schema(tags=["Categories"])
class CategoryViewSet(viewsets.ReadOnlyModelViewSet, BaseResponseMixin):
    """
    API endpoint for managing product categories.
    Supports hierarchical category structures with parent-child relationships.
    """

    queryset = Category.objects.all()
    permission_classes = [IsAuthenticated]
    throttle_classes = [CategoryRateThrottle]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_map = {
            "list": CategoryListSerializer,
            "tree": CategoryTreeSerializer,
        }
        return serializer_map.get(self.action, CategoryDetailSerializer)

    def get_queryset(self):
        """Optimize queryset based on action."""
        base_queryset = super().get_queryset()

        if self.action == "list":
            # Set up caching parameters
            include_inactive = self.request.query_params.get("include_inactive", False)

            # Generate cache key
            cache_key = CacheKeyManager.make_key(
                "category", "list", include_inactive=include_inactive
            )

            # Check cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Don't delegate to CategoryService, handle it here
            queryset = base_queryset
            if not include_inactive:
                queryset = queryset.filter(is_active=True)

            # Build the optimized queryset
            result = (
                queryset.select_related("parent")
                .prefetch_related(
                    Prefetch(
                        "subcategories",
                        queryset=Category.objects.select_related("parent")
                        .annotate(
                            product_count=Count("products", distinct=True),
                            children_count=Count("subcategories", distinct=True),
                        )
                        .filter(is_active=True),
                    ),
                    "products",
                )
                .annotate(
                    product_count=Count("products", distinct=True),
                    children_count=Count("subcategories", distinct=True),
                )
            )

            # Evaluate the queryset to execute the database query
            evaluated_result = list(result)

            # Cache the evaluated result
            cache.set(cache_key, evaluated_result)
            return evaluated_result

        elif self.action in ["retrieve"]:
            return base_queryset.select_related("parent").filter(is_active=True)

        return base_queryset

    @extend_schema(**category_viewset_schema.get("tree", {}))
    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Get hierarchical tree of categories."""
        max_depth = min(int(request.query_params.get("depth", 3)), 5)  # Limit depth
        include_inactive = (
            request.query_params.get("include_inactive", "false").lower() == "true"
        )

        tree_data = CategoryService.get_category_tree(max_depth, include_inactive)
        return Response(tree_data)

    @extend_schema(**category_viewset_schema.get("subcategories", {}))
    @action(detail=True, methods=["get"])
    def subcategories(self, request, pk=None):
        """Get direct subcategories of a specific category."""
        category = self.get_object()
        subcategories = category.subcategories.filter(is_active=True).select_related(
            "parent"
        )

        serializer = CategoryListSerializer(
            subcategories, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(**category_viewset_schema.get("products", {}))
    @action(detail=True, methods=["get"])
    def products(self, request, pk=None):
        """Get products belonging to this category."""
        from apps.products.product_base.serializers import ProductListSerializer

        # Parse filters
        filters = {}
        for param in ["price_min", "price_max", "brand", "in_stock"]:
            if param in request.query_params:
                filters[param] = request.query_params[param]

        include_subcategories = (
            request.query_params.get("include_subcategories", "false").lower() == "true"
        )

        result = CategoryService.get_category_with_products(
            pk, include_subcategories, filters
        )

        if not result:
            return self.error_response(
                message="Category not found", status_code=status.HTTP_404_NOT_FOUND
            )

        # Apply pagination
        products = result["products"]
        page = self.paginate_queryset(products)

        if page is not None:
            serializer = ProductListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = ProductListSerializer(
            products, many=True, context={"request": request}
        )
        return self.success_response(data=serializer.data)

    @extend_schema(**category_viewset_schema.get("popular", {}))
    @action(detail=False, methods=["get"])
    def popular(self, request):
        """Get most popular categories based on product count."""
        limit = min(int(request.query_params.get("limit", 10)), 50)  # Limit to 50

        categories = CategoryService.get_popular_categories(limit)
        serializer = CategoryListSerializer(
            categories, many=True, context={"request": request}
        )
        return Response(serializer.data)


class CategoryAdminViewSet(BaseViewSet):
    """
    Admin-only endpoint for managing categories, including inactive ones.
    """

    # queryset = Category.objects.all()
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["id", "name", "slug", "parent_id"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "product_count", "children_count"]
    ordering = ["name"]

    def get_queryset(self):
        return (
            Category.objects.select_related("parent")
            .prefetch_related("subcategories", "products")
            .annotate(
                product_count=Count("products", distinct=True),
                children_count=Count("subcategories", distinct=True),
            )
        )

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update", "bulk_create"]:
            return CategoryWriteSerializer
        if self.action == "list":
            return CategoryListSerializer
        return CategoryDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Add depth control for nested serialization
        context["depth"] = self.request.query_params.get("depth", 1)
        return context

    def create(self, request, *args, **kwargs):
        """Override default create to use our custom create_category method."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Use our custom create method
            category = CategoryService.create_category(serializer.validated_data)

            # Serialize the created category for response
            response_serializer = self.get_serializer(category)
            return self.success_response(
                data=response_serializer.data, status_code=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating category: {str(e)}")
            return self.error_response(
                message="Failed to create category",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def update(self, request, *args, **kwargs):
        """Override default update to use our custom update_category method."""
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()

            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)

            # Use our custom update method
            updated_category = CategoryService.update_category(
                instance.id, serializer.validated_data
            )

            # Serialize the updated category for response
            response_serializer = self.get_serializer(updated_category)
            return self.success_response(data=response_serializer.data)

        except ValidationError as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating category: {str(e)}")
            return self.error_response(
                message="Failed to update category",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        Optimized bulk create endpoint with enhanced error handling.
        """
        try:
            # Debug: Log the incoming request data
            logger.info(f"Bulk create request data: {request.data}")

            categories_data = request.data.get("categories", [])

            if not categories_data:
                return self.error_response(
                    message="No categories data provided",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if not isinstance(categories_data, list):
                return self.error_response(
                    message="Categories must be a list",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Pre-validate all data before processing
            validated_categories = []
            for i, category_data in enumerate(categories_data):
                try:
                    # Debug: Log each category data
                    logger.info(f"Processing category {i}: {category_data}")

                    # Ensure category_data is a dictionary
                    if not isinstance(category_data, dict):
                        return self.error_response(
                            message=f"Category data at index {i} must be a dictionary, got {type(category_data)}",
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )

                    # Create a copy to avoid modifying the original
                    processed_data = category_data.copy()

                    # Handle parent_name resolution
                    if (
                        "parent_name" in processed_data
                        and processed_data["parent_name"] is not None
                    ):
                        try:
                            parent_category = Category.objects.get(
                                name=processed_data["parent_name"]
                            )
                            processed_data["parent"] = parent_category.id
                            del processed_data["parent_name"]
                        except Category.DoesNotExist:
                            return self.error_response(
                                message=f"Parent category '{processed_data['parent_name']}' not found at index {i}",
                                status_code=status.HTTP_400_BAD_REQUEST,
                            )
                        except Exception as e:
                            logger.error(
                                f"Error resolving parent_name at index {i}: {str(e)}"
                            )
                            return self.error_response(
                                message=f"Error resolving parent category at index {i}: {str(e)}",
                                status_code=status.HTTP_400_BAD_REQUEST,
                            )

                    # Validate serializer data
                    serializer = self.get_serializer(data=processed_data)
                    if not serializer.is_valid():
                        logger.error(
                            f"Serializer validation failed for category {i}: {serializer.errors}"
                        )
                        return self.error_response(
                            message=f"Invalid data for category at index {i}: {serializer.errors}",
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )

                    validated_categories.append(serializer.validated_data)

                except Exception as e:
                    logger.error(f"Error processing category at index {i}: {str(e)}")
                    return self.error_response(
                        message=f"Error processing category at index {i}: {str(e)}",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Use optimized bulk create
            created_categories = CategoryService.bulk_create_categories(
                validated_categories
            )

            # Serialize response with optimized queries
            response_serializer = self.get_serializer(created_categories, many=True)

            return self.success_response(
                message=f"Successfully created {len(created_categories)} categories",
                data=response_serializer.data,
                status_code=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            logger.error(f"Validation error in bulk create: {str(e)}")
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error in bulk create: {str(e)}", exc_info=True)
            return self.error_response(
                message="Failed to create categories",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CategorySearchView(APIView):
    """
    A view for listing and finding categories.
    Can filter by parent_id to build hierarchies.
    """

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        parent_id = request.query_params.get("parent_id")

        # Start with the base search
        search = CategoryDocument.search()

        if query:
            search = search.query("match", name={"query": query, "fuzziness": "AUTO"})

        # Filter by parent category
        if parent_id:
            if parent_id.lower() == "null":  # Requesting top-level categories
                search = search.filter(
                    "bool", must_not=[Q("exists", field="parent_id")]
                )
            else:
                search = search.filter("term", parent_id=parent_id)

        # Execute and serialize
        # Note: We are not paginating here for simplicity, but you could add it.
        response = search.execute()
        serializer = CategoryListSerializer(response.hits, many=True)

        return Response({"results": serializer.data})

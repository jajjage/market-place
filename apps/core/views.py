from django.http import Http404

# from elasticsearch.dsl.connections import get_connection
# from elasticsearch.dsl import Q

# Import all your documents
from apps.products.product_search.documents import ProductDocument
from apps.products.product_brand.documents import BrandDocument
from apps.categories.documents import CategoryDocument  # Adjust path if needed

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


class BaseResponseMixin:
    """Mixin to standardize API responses."""

    """
    Base API View that standardizes response format across the application.
    All responses will have the format:
    {
        "status": "success" | "error",
        "message": str,
        "data": Any | None
    }
    """

    def success_response(
        self, data=None, message="Success", status_code=status.HTTP_200_OK
    ):
        """Send a success response"""
        response_data = {
            "status": "success",
            "status_code": status_code,
            "message": message,
            "data": data,
        }
        return Response(response_data, status=status_code)

    def error_response(
        self,
        message="An error occurred",
        status_code=status.HTTP_400_BAD_REQUEST,
        data=None,
    ):
        """Send an error response"""
        response_data = {
            "status": "error",
            "message": message,
            "data": data,
            "status_code": status_code,
        }
        return Response(response_data, status=status_code)


class BaseViewSet(ModelViewSet, BaseResponseMixin):
    """
    Base ViewSet for patient-related models with standardized CRUD operations,
    plus configurable caching on `list` and `retrieve`.
    """

    # === CONFIGURABLE CACHE TIMEOUTS ===
    # Subclasses can override these. If set to an integer (seconds),
    # the corresponding method will be wrapped in cache_page(timeout).
    cache_list_seconds = None
    cache_retrieve_seconds = None

    # ------------------------------------
    # CREATE
    # ------------------------------------
    def create(self, request, *args, **kwargs):
        """
        Standardized create method with proper error handling and response format.
        """
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} created successfully",
                status_code=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except (TypeError, AttributeError, PermissionError) as e:
            return self.error_response(
                message=f"Failed to create {self.get_model_name().lower()}: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------
    # UPDATE
    # ------------------------------------
    def update(self, request, *args, **kwargs):
        """
        Standardized update method with proper error handling and response format.
        """
        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} updated successfully",
            )
        except ValidationError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except (PermissionError, AttributeError, TypeError) as e:
            return self.error_response(
                message=f"Failed to update {self.get_model_name().lower()}: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------
    # DESTROY
    # ------------------------------------
    def destroy(self, request, *args, **kwargs):
        """
        Standardized delete method with proper error handling and response format.
        """
        try:
            instance = self.get_object()
            self.perform_destroy(instance)

            return self.success_response(
                message=f"{self.get_model_name()} deleted successfully",
                status_code=status.HTTP_204_NO_CONTENT,
            )
        except (Http404, PermissionError, ValidationError) as e:
            return self.error_response(
                message=f"Failed to delete {self.get_model_name().lower()}: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------
    # LIST
    # ------------------------------------
    def list(self, request, *args, **kwargs):
        """
        The core `list` logic—pulled out so we can wrap it in cache_page if needed.
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} list retrieved successfully",
            )
        except (ValidationError, PermissionError):
            return self.error_response(
                message=f"Failed to retrieve {self.get_model_name().lower()} list",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except (TypeError, AttributeError) as e:
            return self.error_response(
                message=f"Error processing {self.get_model_name().lower()} list: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------
    # RETRIEVE
    # ------------------------------------
    def retrieve(self, request, *args, **kwargs):
        """
        The core `retrieve` logic—pulled out so we can wrap it in cache_page if needed.
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return self.success_response(
                data=serializer.data,
                message=f"{self.get_model_name()} retrieved successfully",
            )
        except Http404:
            return self.error_response(
                message=f"{self.get_model_name()} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except (ValidationError, PermissionError) as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    # ------------------------------------
    # HELPER
    # ------------------------------------
    def get_model_name(self) -> str:
        """
        Helper method to get the model name for messages.
        """
        return self.__class__.__name__.replace("ViewSet", "")


class BaseAPIView(APIView):
    """
    Base API View that standardizes response format across the application.
    All responses will have the format:
    {
        "status": "success" | "error",
        "message": str,
        "data": Any | None
    }
    """

    def success_response(
        self, data=None, message="Success", status_code=status.HTTP_200_OK
    ):
        """Send a success response"""
        response_data = {
            "status": "success",
            "status_code": status_code,
            "message": message,
            "data": data,
        }
        return Response(response_data, status=status_code)

    def error_response(
        self,
        message="An error occurred",
        status_code=status.HTTP_400_BAD_REQUEST,
        data=None,
    ):
        """Send an error response"""
        response_data = {
            "status": "error",
            "message": message,
            "data": data,
            "status_code": status_code,
        }
        return Response(response_data, status=status_code)


class UnifiedAutocompleteView(APIView):
    """
    A powerful autocomplete that uses the edge_ngram analyzer
    for fast, partial-word matching across all relevant documents.
    """

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response({"suggestions": []})

        suggestions = []

        # A helper to prevent duplicate suggestions
        seen = set()

        # 1. Search Brands using the 'name.autocomplete' field
        brand_search = BrandDocument.search().query(
            "match", **{"name.autocomplete": query}
        )[:3]
        for hit in brand_search.execute():
            if hit.name not in seen:
                suggestions.append(
                    {"text": hit.name, "type": "brand", "slug": hit.slug}
                )
                seen.add(hit.name)

        # 2. Search Categories using the 'name.autocomplete' field
        category_search = CategoryDocument.search().query(
            "match", **{"name.autocomplete": query}
        )[:3]
        for hit in category_search.execute():
            if hit.name not in seen:
                suggestions.append(
                    {"text": hit.name, "type": "category", "slug": hit.slug}
                )
                seen.add(hit.name)

        # 3. Search Products using its autocomplete fields
        product_search = ProductDocument.search().query(
            "multi_match",
            query=query,
            fields=["title.autocomplete^2", "search_text.autocomplete"],
        )[:5]
        for hit in product_search.execute():
            if hit.title not in seen:
                suggestions.append(
                    {"text": hit.title, "type": "product", "slug": hit.slug}
                )
                seen.add(hit.title)

        return Response({"suggestions": suggestions})

from django.db import connections
from elasticsearch import NotFoundError
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination

from apps.products.documents import ProductDocument
from apps.products.serializers import (
    ProductSearchListSerializer,
    ProductSearchResponseSerializer,
    ProductSearchFacetSerializer,
)
from apps.products.services.search import SearchCoordinator, SearchQuery

import logging

logger = logging.getLogger(__name__)


class ProductSearchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ProductSearchView(APIView):
    """
    Main product search endpoint with SEO optimization.
    Delegates querying and analytics to the SearchCoordinator.
    """

    permission_classes = [AllowAny]
    search_coordinator = SearchCoordinator()

    def get(self, request):
        try:
            query = request.query_params.get("q", "").strip()
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)
            sort_by = request.query_params.get("sort", "relevance")

            logger.info(f"Search view: query: {query}, page: {page}, page_size: {page_size}")

            # Get client info for analytics logging
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT", "")

            # Formulate the search query DTO
            search_query = SearchQuery(
                query_text=query,
                filters=request.query_params,
                sort_by=sort_by,
                page=page,
                page_size=page_size,
                ip_address=ip_address,
                user_agent=user_agent,
                user=request.user,
            )

            # Delegate search execution
            search_response = self.search_coordinator.execute_search(search_query)

            # Serialize results and facets
            serializer = ProductSearchListSerializer(search_response.results, many=True)
            facet_serializer = ProductSearchFacetSerializer(search_response.facets)

            # Format paginated response
            response_data = {
                "results": serializer.data,
                "facets": facet_serializer.data,
                "total_count": search_response.total_count,
                "page": search_response.page,
                "page_size": search_response.page_size,
                "total_pages": search_response.total_pages,
                "query": search_response.query,
                "took": search_response.took,
            }

            response_serializer = ProductSearchResponseSerializer(response_data)
            return Response(response_serializer.data)

        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Search failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_client_ip(self, request):
        """Helper to resolve client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR", "")


class ElasticsearchDebugView(APIView):
    """Debug view to test Elasticsearch connection and index status."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            search = ProductDocument.search()
            response = search.execute()

            sample_search = ProductDocument.search()[:5]
            sample_response = sample_search.execute()

            debug_info = {
                "elasticsearch_connected": True,
                "index_name": ProductDocument._index._name,
                "total_documents": response.hits.total.value,
                "sample_documents": [
                    {
                        "id": hit.meta.id,
                        "title": getattr(hit, "title", "N/A"),
                        "price": getattr(hit, "price", "N/A"),
                        "brand_name": getattr(hit, "brand_name", "N/A"),
                        "is_active": getattr(hit, "is_active", "N/A"),
                    }
                    for hit in sample_response
                ],
                "search_fields_available": [
                    "title",
                    "description",
                    "brand_name",
                    "category_name",
                    "price",
                    "is_active",
                    "status",
                    "location",
                ],
            }
            return Response(debug_info)

        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {str(e)}")
            return Response(
                {
                    "elasticsearch_connected": False,
                    "error": str(e),
                    "suggestion": "Check if Elasticsearch is running and index exists",
                }
            )


class ProductRelatedSearchView(APIView):
    """
    Find related/similar products based on a reference product.
    Delegates logic to the SearchCoordinator.
    """

    permission_classes = [AllowAny]
    search_coordinator = SearchCoordinator()

    def get(self, request, product_id):
        try:
            data = self.search_coordinator.execute_find_related(
                str(product_id), limit=20
            )
            serialized_data = ProductSearchListSerializer(
                data["results"], many=True
            ).data

            return Response(
                {
                    "related_products": serialized_data,
                    "total": len(serialized_data),
                    "reference_product_id": str(product_id),
                    "debug_info": data["debug_info"],
                    "elasticsearch_total": data["total_count"],
                }
            )
        except NotFoundError as e:
            logger.error(f"Product ID {product_id} not found: {e}")
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error fetching related products for ID {product_id}")
            return Response(
                {"error": "Failed to retrieve related products"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProductAutocompleteView(APIView):
    """
    Autocomplete endpoint for search suggestions.
    Delegates to the SearchCoordinator.
    """

    permission_classes = [AllowAny]
    search_coordinator = SearchCoordinator()

    def get(self, request):
        query = request.query_params.get("q", "").strip()

        if not query or len(query) < 2:
            return Response({"suggestions": []})

        try:
            suggestions = self.search_coordinator.execute_autocomplete(
                query, limit=10
            )
            return Response({"suggestions": suggestions})
        except Exception as e:
            logger.error(f"Autocomplete search failed: {str(e)}", exc_info=True)
            return Response({"suggestions": []})


class ProductSEOSearchView(APIView):
    """
    SEO-optimized search endpoint.
    Delegates to the SearchCoordinator.
    """

    permission_classes = [AllowAny]
    search_coordinator = SearchCoordinator()

    def get(self, request):
        category_slug = request.query_params.get("category")
        brand_slug = request.query_params.get("brand")
        location = request.query_params.get("location")

        try:
            data = self.search_coordinator.execute_seo_search(
                category_slug=category_slug,
                brand_slug=brand_slug,
                location=location,
                limit=50,
            )

            serializer = ProductSearchListSerializer(data["results"], many=True)

            return Response(
                {
                    "results": serializer.data,
                    "total": data["total_count"],
                    "seo_data": {
                        "category": category_slug,
                        "brand": brand_slug,
                        "location": location,
                    },
                    "meta": {
                        "page_title": self._generate_seo_title(
                            category_slug, brand_slug, location
                        ),
                        "page_description": self._generate_seo_description(
                            category_slug, brand_slug, location
                        ),
                    },
                }
            )
        except Exception as e:
            logger.error(f"SEO search failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "SEO search failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _generate_seo_title(self, category, brand, location):
        """Generate SEO-friendly page title."""
        parts = []
        if brand:
            parts.append(brand.replace("-", " ").title())
        if category:
            parts.append(category.replace("-", " ").title())
        if location:
            parts.append(f"in {location}")

        if parts:
            return f"{' '.join(parts)} - Buy & Sell Online"
        return "Products - Buy & Sell Online"

    def _generate_seo_description(self, category, brand, location):
        """Generate SEO-friendly meta description."""
        parts = []
        if brand:
            parts.append(brand.replace("-", " ").title())
        if category:
            parts.append(category.replace("-", " ").title())
        if location:
            parts.append(f"in {location}")

        if parts:
            return f"Find {' '.join(parts)} at the best prices. Buy and sell with confidence."
        return "Discover amazing products at great prices. Buy and sell with confidence on our marketplace."


class ProductSearchStatsView(APIView):
    """
    Search statistics endpoint for analytics.
    Delegates to the SearchCoordinator.
    """

    permission_classes = [AllowAny]
    search_coordinator = SearchCoordinator()

    def get(self, request):
        try:
            stats = self.search_coordinator.execute_get_stats()
            return Response(stats)
        except Exception as e:
            logger.error(f"Stats retrieval failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Stats retrieval failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

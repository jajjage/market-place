from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from elasticsearch_dsl import Q
from .documents import ProductDocument
from .serializers import (
    ProductSearchListSerializer,
    ProductSearchSuggestionSerializer,
    ProductSearchResponseSerializer,
    ProductSearchFacetSerializer,
)

import logging

logger = logging.getLogger(__name__)


class ProductSearchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ProductSearchView(APIView):
    """
    Main product search endpoint with SEO optimization
    Supports full-text search, filters, sorting, and autocomplete
    """

    def get(self, request):
        try:
            query = request.query_params.get("q", "").strip()
            page = int(request.query_params.get("page", 1))
            page_size = min(int(request.query_params.get("page_size", 20)), 100)

            logger.info(f"Search query: {query}, page: {page}, page_size: {page_size}")

            # Initialize search
            search = ProductDocument.search()

            # Apply basic filters (only active products)
            search = search.filter("term", is_active=True)
            search = search.filter("term", status="active")

            # Full-text search
            if query:
                search = self._apply_text_search(search, query)
                logger.info(f"Applied text search for query: {query}")

            # Apply filters
            search = self._apply_filters(search, request.query_params)

            # Apply sorting
            search = self._apply_sorting(search, request.query_params)

            # Store search for aggregations before pagination
            agg_search = search[:0]  # Clone for aggregations

            # Apply pagination
            search = self._apply_pagination(search, request.query_params)

            # Execute search
            response = search.execute()
            logger.info(
                f"Search executed successfully. Total hits: {response.hits.total.value}"
            )

            # Get aggregations
            aggregations = self._get_aggregations(agg_search)
            logger.info(f"Aggregations retrieved: {aggregations}")

            # Serialize results
            serializer = ProductSearchListSerializer(response, many=True)
            logger.info(f"Serialized {len(serializer.data)} products")

            # Serialize facets
            facet_serializer = ProductSearchFacetSerializer(aggregations)

            # Calculate pagination metadata
            total_count = response.hits.total.value
            total_pages = (total_count + page_size - 1) // page_size

            # Prepare complete response
            response_data = {
                "results": serializer.data,
                "facets": facet_serializer.data,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1,
                "query": query,
                "took": response.took,
            }

            # Use complete response serializer
            response_serializer = ProductSearchResponseSerializer(response_data)
            return Response(response_serializer.data)

        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Search failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _apply_text_search(self, search, query):
        """Apply full-text search with boosting"""
        search_query = Q(
            "multi_match",
            query=query,
            fields=[
                "title^3",  # Boost title matches
                "brand_name^2",  # Boost brand matches
                "category_name^2",  # Boost category matches
                "description^1",  # Standard description matches
                "seo_keywords^2",  # Boost SEO keyword matches
                "search_text^1",  # Combined search text
            ],
            type="best_fields",
            fuzziness="AUTO",
        )

        # Add autocomplete boost for partial matches
        autocomplete_query = Q(
            "multi_match",
            query=query,
            fields=[
                "title.autocomplete^2",
                "search_text.autocomplete^1",
            ],
            type="phrase_prefix",
        )

        # Combine queries with different weights
        combined_query = Q("bool", should=[search_query, autocomplete_query])

        return search.query(combined_query)

    def _apply_filters(self, search, params):
        """Apply various filters based on query parameters"""

        # Price range filter
        if params.get("min_price"):
            search = search.filter("range", price={"gte": float(params["min_price"])})
        if params.get("max_price"):
            search = search.filter("range", price={"lte": float(params["max_price"])})

        # Category filter - FIXED
        if params.get("category"):
            categories = params.getlist("category")
            if categories:  # Only apply if list is not empty
                search = search.filter("terms", category_slug=categories)

        # Brand filter - FIXED
        if params.get("brand"):
            brands = params.getlist("brand")
            if brands:  # Only apply if list is not empty
                search = search.filter("terms", brand_name__raw=brands)

        # Condition filter - FIXED
        if params.get("condition"):
            conditions = params.getlist("condition")
            if conditions:  # Only apply if list is not empty
                search = search.filter("terms", condition_name__raw=conditions)

        # Location filter
        if params.get("location"):
            search = search.filter("match", location=params["location"])

        # Boolean filters
        if params.get("is_featured") == "true":
            search = search.filter("term", is_featured=True)

        if params.get("is_negotiable") == "true":
            search = search.filter("term", is_negotiable=True)

        if params.get("authenticity_guaranteed") == "true":
            search = search.filter("term", authenticity_guaranteed=True)

        # Rating filter
        if params.get("min_rating"):
            search = search.filter(
                "range", average_rating={"gte": float(params["min_rating"])}
            )

        return search

    def _apply_sorting(self, search, params):
        """Apply sorting based on query parameters"""
        sort_by = params.get("sort", "relevance")

        logger.info(f"Applying sort: {sort_by}")

        if sort_by == "price_asc":
            search = search.sort("price")
        elif sort_by == "price_desc":
            search = search.sort("-price")
        elif sort_by == "newest":
            search = search.sort("-created_at")
        elif sort_by == "oldest":
            search = search.sort("created_at")
        elif sort_by == "rating":
            search = search.sort("-average_rating", "-rating_count")
        elif sort_by == "popularity":
            search = search.sort("-popularity_score")
        elif sort_by == "views":
            search = search.sort("-views_count")
        # Default is relevance (score), no explicit sort needed

        return search

    def _apply_pagination(self, search, params):
        """Apply pagination"""
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))

        # Ensure page_size doesn't exceed maximum
        page_size = min(page_size, 100)

        start = (page - 1) * page_size
        end = start + page_size

        logger.info(
            f"Pagination: page={page}, page_size={page_size}, start={start}, end={end}"
        )

        return search[start:end]

    def _get_aggregations(self, search):
        """Get aggregations for faceted search"""
        try:
            # Add aggregations
            search.aggs.bucket("brands", "terms", field="brand_name.raw", size=20)
            search.aggs.bucket(
                "categories", "terms", field="category_name.raw", size=20
            )
            search.aggs.bucket(
                "conditions", "terms", field="condition_name.raw", size=10
            )
            search.aggs.bucket("locations", "terms", field="location.raw", size=20)

            # Price range aggregation
            search.aggs.bucket(
                "price_ranges",
                "range",
                field="price",
                ranges=[
                    {"key": "under_100", "to": 100},
                    {"key": "100_500", "from": 100, "to": 500},
                    {"key": "500_1000", "from": 500, "to": 1000},
                    {"key": "1000_5000", "from": 1000, "to": 5000},
                    {"key": "over_5000", "from": 5000},
                ],
            )

            # Rating aggregation
            search.aggs.bucket(
                "ratings",
                "range",
                field="average_rating",
                ranges=[
                    {"key": "4_and_up", "from": 4.0},
                    {"key": "3_and_up", "from": 3.0},
                    {"key": "2_and_up", "from": 2.0},
                    {"key": "1_and_up", "from": 1.0},
                ],
            )

            agg_response = search.execute()
            return {
                "brands": [
                    {"key": b.key, "count": b.doc_count}
                    for b in agg_response.aggregations.brands.buckets
                ],
                "categories": [
                    {"key": c.key, "count": c.doc_count}
                    for c in agg_response.aggregations.categories.buckets
                ],
                "conditions": [
                    {"key": c.key, "count": c.doc_count}
                    for c in agg_response.aggregations.conditions.buckets
                ],
                "locations": [
                    {"key": location.key, "count": location.doc_count}
                    for location in agg_response.aggregations.locations.buckets
                ],
                "price_ranges": [
                    {"key": p.key, "count": p.doc_count}
                    for p in agg_response.aggregations.price_ranges.buckets
                ],
                "ratings": [
                    {"key": r.key, "count": r.doc_count}
                    for r in agg_response.aggregations.ratings.buckets
                ],
            }
        except Exception as e:
            logger.error(f"Failed to retrieve aggregations: {str(e)}")
            return {
                "brands": [],
                "categories": [],
                "conditions": [],
                "locations": [],
                "price_ranges": [],
                "ratings": [],
            }


# Add a debug view to test your Elasticsearch connection
class ElasticsearchDebugView(APIView):
    """Debug view to test Elasticsearch connection and index status"""

    def get(self, request):
        try:
            # Test basic connection
            search = ProductDocument.search()

            # Get index stats
            response = search.execute()

            # Get some sample documents
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
            return (
                Response(
                    {
                        "elasticsearch_connected": False,
                        "error": str(e),
                        "suggestion": "Check if Elasticsearch is running and index exists",
                    }
                ),
            )


class ProductRelatedSearchView(APIView):
    """
    Find related/similar products based on a reference product
    Used for "You might also like" or "Similar products" features
    """

    def get(self, request, product_id):
        try:
            # Get the reference product first (from your main Product model/API)
            reference_product = self._get_reference_product(product_id)

            # Build "More Like This" query
            search = ProductDocument.search()
            search = search.filter("term", is_active=True)
            search = search.filter("term", status="active")
            search = search.exclude(
                "term", _id=product_id
            )  # Exclude the reference product

            # More Like This query based on title, description, and category
            mlt_query = Q(
                "more_like_this",
                fields=["title", "description", "category_name", "brand_name"],
                like=[{"_index": "products", "_id": product_id}],
                min_term_freq=1,
                max_query_terms=12,
            )

            search = search.query(mlt_query)

            # Boost products from same category and brand
            search = search.query(
                Q(
                    "bool",
                    should=[
                        Q("term", category_id=reference_product.get("category_id")),
                        Q("term", brand_id=reference_product.get("brand_id")),
                    ],
                )
            )

            # Sort by relevance and popularity
            search = search.sort("_score", "-popularity_score")
            search = search[:12]  # Limit to 12 related products

            response = search.execute()
            serializer = ProductSearchListSerializer(response, many=True)

            return Response(
                {
                    "related_products": serializer.data,
                    "total": len(serializer.data),
                    "reference_product_id": product_id,
                }
            )

        except Exception as e:
            return Response(
                {"error": "Related products search failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_reference_product(self, product_id):
        """Get basic info about reference product - implement based on your Product model"""
        try:
            # This should call your main Product model/API
            # return Product.objects.get(id=product_id)
            # For now, get from Elasticsearch
            product = ProductDocument.get(id=product_id)
            return product.to_dict()
        except:
            raise Exception("Reference product not found")


class ProductAutocompleteView(APIView):
    """
    Autocomplete endpoint for search suggestions
    Optimized for fast response times
    """

    def get(self, request):
        query = request.query_params.get("q", "").strip()

        if not query or len(query) < 2:
            return Response({"suggestions": []})

        # Use completion suggester for fast autocomplete
        search = ProductDocument.search()

        # Title suggestions
        search = search.suggest(
            "title_suggest", query, completion={"field": "title.suggest", "size": 5}
        )

        # Brand suggestions
        search = search.suggest(
            "brand_suggest",
            query,
            completion={"field": "brand_name.suggest", "size": 3},
        )

        # Also do a quick text search for popular items
        text_search = ProductDocument.search()
        text_search = text_search.filter("term", is_active=True)
        text_search = text_search.query(
            "multi_match",
            query=query,
            fields=["title.autocomplete^2", "brand_name^1"],
            type="phrase_prefix",
        )
        text_search = text_search.sort("-popularity_score")
        text_search = text_search[:5]

        try:
            response = search.execute()
            text_response = text_search.execute()

            # Collect all suggestions
            all_suggestions = []

            # Add completion suggestions
            for option in response.suggest.title_suggest[0].options:
                all_suggestions.append(
                    {"text": option.text, "type": "product", "score": option.score}
                )

            for option in response.suggest.brand_suggest[0].options:
                all_suggestions.append(
                    {"text": option.text, "type": "brand", "score": option.score}
                )

            # Add popular product suggestions with serializer
            serializer = ProductSearchSuggestionSerializer(text_response, many=True)
            for item in serializer.data:
                all_suggestions.append(
                    {
                        "text": item["title"],
                        "type": "popular",
                        "score": item.get("popularity_score", 0),
                        "id": item.get("id"),
                        "slug": item["slug"],
                        "price": item["price"],
                        "currency": item["currency"],
                    }
                )

            # Remove duplicates and sort by score
            seen = set()
            unique_suggestions = []
            for suggestion in all_suggestions:
                text_lower = suggestion["text"].lower()
                if text_lower not in seen:
                    seen.add(text_lower)
                    unique_suggestions.append(suggestion)

            # Sort by score and limit
            unique_suggestions.sort(key=lambda x: x.get("score", 0), reverse=True)

            return Response({"suggestions": unique_suggestions[:10]})

        except Exception as e:
            return Response({"suggestions": []})


class ProductSEOSearchView(APIView):
    """
    SEO-optimized search endpoint
    Designed for search engines and SEO-friendly URLs
    """

    def get(self, request):
        # Extract SEO parameters
        category_slug = request.query_params.get("category")
        brand_slug = request.query_params.get("brand")
        location = request.query_params.get("location")

        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")

        # Apply SEO filters
        if category_slug:
            search = search.filter("term", category_slug=category_slug)

        if brand_slug:
            search = search.filter("term", brand_name__raw=brand_slug)

        if location:
            search = search.filter("match", location=location)

        # Sort by popularity for SEO
        search = search.sort("-popularity_score", "-views_count")

        # Limit results for SEO pages
        search = search[:50]

        try:
            response = search.execute()

            # Use serializer for consistent data format
            serializer = ProductSearchListSerializer(response, many=True)

            return Response(
                {
                    "results": serializer.data,
                    "total": response.hits.total.value,
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
            return Response(
                {"error": "SEO search failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _generate_seo_title(self, category, brand, location):
        """Generate SEO-friendly page title"""
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
        """Generate SEO-friendly meta description"""
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
    Search statistics endpoint for analytics
    """

    def get(self, request):
        try:
            # Get basic stats
            search = ProductDocument.search()
            search = search.filter("term", is_active=True)

            # Add aggregations for stats
            search.aggs.bucket("total_products", "value_count", field="_id")
            search.aggs.bucket("avg_price", "avg", field="price")
            search.aggs.bucket("categories_count", "cardinality", field="category_id")
            search.aggs.bucket("brands_count", "cardinality", field="brand_id")
            search.aggs.bucket(
                "featured_count", "filter", filter={"term": {"is_featured": True}}
            )

            # Execute with no results, only aggregations
            search = search[:0]
            response = search.execute()

            stats = {
                "total_products": response.aggregations.total_products.value,
                "average_price": round(response.aggregations.avg_price.value or 0, 2),
                "total_categories": response.aggregations.categories_count.value,
                "total_brands": response.aggregations.brands_count.value,
                "featured_products": response.aggregations.featured_count.doc_count,
            }

            return Response(stats)

        except Exception as e:
            return Response(
                {"error": "Stats retrieval failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

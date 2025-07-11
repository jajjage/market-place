from django.db import connections
from elasticsearch import NotFoundError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from elasticsearch_dsl import Q
from .documents import ProductDocument
from .serializers import (
    ProductSearchListSerializer,
    # ProductSearchSuggestionSerializer,
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
    Find related/similar products based on a reference product using Elasticsearch.
    Enhanced version with debugging capabilities.
    """

    def get(self, request, product_id):
        try:
            reference_product_doc = self._get_reference_product_from_es(product_id)
            if not reference_product_doc:
                return Response(
                    {"error": f"Reference product with ID '{product_id}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            reference_product_data = reference_product_doc.to_dict()

            # DEBUG: Log reference product data
            logger.info(f"Reference product data: {reference_product_data}")

            # --- Start building a list of "should" clauses for our main query ---
            all_should_queries = []
            debug_info = {"queries_added": []}

            # 1. Add the More Like This (MLT) query with a VERY HIGH boost.
            mlt_fields = [
                f
                for f in [
                    "title^3",
                    "description^2",
                    "seo_keywords^2.5",
                    "category_name^1.5",
                    "brand_name^0.8",
                ]
                if reference_product_data.get(f.split("^")[0])
            ]

            if mlt_fields:
                mlt_like_item = {
                    "_index": reference_product_doc.meta.index,
                    "_id": product_id,
                }
                mlt_query = Q(
                    "more_like_this",
                    fields=mlt_fields,
                    like=[mlt_like_item],
                    min_term_freq=1,
                    min_doc_freq=1,
                    max_query_terms=25,
                    minimum_should_match="10%",  # Reduced from 20% to be less strict
                    boost=4.0,
                )
                all_should_queries.append(mlt_query)
                debug_info["queries_added"].append(
                    f"MLT query with fields: {mlt_fields}"
                )

            # 2. Add boosting for shared CATEGORY
            if category_id := reference_product_data.get("category_id"):
                all_should_queries.append(
                    Q("term", category_id={"value": category_id, "boost": 2.5})
                )
                debug_info["queries_added"].append(f"Category ID: {category_id}")
            elif category_name := reference_product_data.get("category_name"):
                # Fallback to category_name if category_id is not available
                all_should_queries.append(
                    Q(
                        "term",
                        **{
                            "category_name.keyword": {
                                "value": category_name,
                                "boost": 2.5,
                            }
                        },
                    )
                )
                debug_info["queries_added"].append(f"Category Name: {category_name}")

            # 3. Add boosting for shared BRAND
            if brand_id := reference_product_data.get("brand_id"):
                all_should_queries.append(
                    Q("term", brand_id={"value": brand_id, "boost": 2.0})
                )
                debug_info["queries_added"].append(f"Brand ID: {brand_id}")
            elif brand_name := reference_product_data.get("brand_name"):
                # Fallback to brand_name if brand_id is not available
                all_should_queries.append(
                    Q(
                        "term",
                        **{"brand_name.keyword": {"value": brand_name, "boost": 2.0}},
                    )
                )
                debug_info["queries_added"].append(f"Brand Name: {brand_name}")

            # 4. Add boosting for shared CONDITION
            if condition_id := reference_product_data.get("condition_id"):
                all_should_queries.append(
                    Q("term", condition_id={"value": condition_id, "boost": 1.5})
                )
                debug_info["queries_added"].append(f"Condition ID: {condition_id}")
            elif condition_name := reference_product_data.get("condition_name"):
                # Fallback to condition_name if condition_id is not available
                all_should_queries.append(
                    Q(
                        "term",
                        **{
                            "condition_name.keyword": {
                                "value": condition_name,
                                "boost": 1.5,
                            }
                        },
                    )
                )
                debug_info["queries_added"].append(f"Condition Name: {condition_name}")

            # 5. Add exact title match for duplicate titles (like "Babbar Riga")
            if title := reference_product_data.get("title"):
                all_should_queries.append(
                    Q("term", **{"title.keyword": {"value": title, "boost": 3.0}})
                )
                debug_info["queries_added"].append(f"Exact Title: {title}")

            # --- Build and Execute the Final Query ---
            search = ProductDocument.search()
            search = search.filter("term", is_active=True)
            search = search.filter("term", status="active")
            search = search.exclude("term", _id=product_id)

            if not all_should_queries:
                debug_info["error"] = "No should queries generated"
                return Response(
                    {
                        "related_products": [],
                        "total": 0,
                        "reference_product_id": product_id,
                        "debug_info": debug_info,
                    }
                )

            # Combine all clauses into a single bool query
            final_query = Q("bool", should=all_should_queries, minimum_should_match=1)
            search = search.query(final_query)

            # DEBUG: Log the actual query being executed
            logger.info(f"Elasticsearch query: {search.to_dict()}")
            debug_info["elasticsearch_query"] = search.to_dict()

            # --- Sort and Paginate/Limit Results ---
            search = search.sort(
                {"_score": {"order": "desc"}}, {"popularity_score": {"order": "desc"}}
            )
            search = search[:20]  # Increased limit to see more results

            # --- Execute Search and Serialize Response ---
            response = search.execute()

            # DEBUG: Log raw response
            logger.info(f"Raw ES response - Total hits: {response.hits.total}")
            for hit in response.hits:
                logger.info(f"Hit: {hit.title} - Score: {hit.meta.score}")

            serialized_data = ProductSearchListSerializer(response.hits, many=True).data

            return Response(
                {
                    "related_products": serialized_data,
                    "total": len(serialized_data),
                    "reference_product_id": product_id,
                    "debug_info": debug_info,
                    "elasticsearch_total": (
                        response.hits.total.value
                        if hasattr(response.hits.total, "value")
                        else response.hits.total
                    ),
                }
            )

        except NotFoundError as e:
            logger.error(f"Product ID {product_id} not found: {e}")
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error fetching related products for ID {product_id}")
            return Response(
                {"error": "Failed to retrieve related products", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_reference_product_from_es(self, product_id):
        try:
            return ProductDocument.get(id=product_id)
        except connections.get_connection().exceptions.NotFoundError:
            raise NotFoundError(
                f"Reference product with ID '{product_id}' not found in Elasticsearch."
            )
        except Exception as e:
            logger.error(
                f"Error retrieving reference product '{product_id}' from ES: {e}"
            )
            raise

    def _debug_check_products_exist(
        self, request, brand_name=None, category_name=None, title=None
    ):
        """
        Debug endpoint to check if products with specific criteria exist in ES
        Usage: GET /api/debug-products/?brand_name=HP&category_name=Cloth&title=Babbar Riga
        """
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")

        if brand_name:
            search = search.filter("term", **{"brand_name.keyword": brand_name})
        if category_name:
            search = search.filter("term", **{"category_name.keyword": category_name})
        if title:
            search = search.filter("term", **{"title.keyword": title})

        search = search[:50]  # Get up to 50 results
        response = search.execute()

        results = []
        for hit in response.hits:
            results.append(
                {
                    "id": hit.meta.id,
                    "title": hit.title,
                    "brand_name": getattr(hit, "brand_name", None),
                    "category_name": getattr(hit, "category_name", None),
                    "is_active": getattr(hit, "is_active", None),
                    "status": getattr(hit, "status", None),
                }
            )

        return Response(
            {
                "total_found": (
                    response.hits.total.value
                    if hasattr(response.hits.total, "value")
                    else response.hits.total
                ),
                "products": results,
                "query": search.to_dict(),
            }
        )


class ProductAutocompleteView(APIView):
    """
    Autocomplete endpoint for search suggestions
    Fixed version that works with basic text fields
    """

    def get(self, request):
        query = request.query_params.get("q", "").strip()

        if not query or len(query) < 2:
            return Response({"suggestions": []})

        try:
            # Use regular text search instead of completion suggester
            search = ProductDocument.search()
            search = search.filter("term", is_active=True)
            search = search.filter("term", status="active")

            # Combine phrase_prefix (for autocomplete) and fuzzy (for typos) in bool query
            phrase_prefix_query = Q(
                "multi_match",
                query=query,
                fields=["title^3", "brand_name^2", "category_name^1"],
                type="phrase_prefix",
            )

            # Fuzzy query for typo tolerance (lower boost)
            fuzzy_query = Q(
                "multi_match",
                query=query,
                fields=["title^1.5", "brand_name^1", "category_name^0.5"],
                fuzziness="AUTO",
            )

            # Combine both queries
            combined_query = Q(
                "bool",
                should=[phrase_prefix_query, fuzzy_query],
                minimum_should_match=1,
            )

            search = search.query(combined_query)

            # Sort by relevance score and popularity
            search = search.sort(
                {"_score": {"order": "desc"}}, {"popularity_score": {"order": "desc"}}
            )
            search = search[:10]  # Limit results

            response = search.execute()

            # Collect suggestions
            suggestions = []
            seen_titles = set()
            seen_brands = set()

            for hit in response.hits:
                # Add product suggestions
                title = hit.title
                if title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    suggestions.append(
                        {
                            "text": title,
                            "type": "product",
                            "score": hit.meta.score,
                            "id": hit.meta.id,
                            "slug": getattr(hit, "slug", ""),
                            "price": getattr(hit, "price", 0),
                            "currency": getattr(hit, "currency", "NGN"),
                            "brand_name": getattr(hit, "brand_name", ""),
                            "category_name": getattr(hit, "category_name", ""),
                        }
                    )

                # Add brand suggestions
                brand_name = getattr(hit, "brand_name", "")
                if (
                    brand_name
                    and brand_name.lower() not in seen_brands
                    and query.lower() in brand_name.lower()
                ):
                    seen_brands.add(brand_name.lower())
                    suggestions.append(
                        {
                            "text": brand_name,
                            "type": "brand",
                            "score": hit.meta.score
                            * 0.8,  # Slightly lower score for brands
                        }
                    )

            # Get additional brand suggestions using aggregation
            brand_search = ProductDocument.search()
            brand_search = brand_search.filter("term", is_active=True)
            brand_search = brand_search.filter("term", status="active")
            brand_search = brand_search.query(
                "wildcard", **{"brand_name.keyword": f"{query}*"}
            )
            brand_search.aggs.bucket(
                "brands", "terms", field="brand_name.keyword", size=5
            )
            brand_search = brand_search[:0]  # We only want aggregation results

            try:
                brand_response = brand_search.execute()
                for bucket in brand_response.aggregations.brands.buckets:
                    brand_name = bucket.key
                    if brand_name.lower() not in seen_brands:
                        seen_brands.add(brand_name.lower())
                        suggestions.append(
                            {
                                "text": brand_name,
                                "type": "brand",
                                "score": bucket.doc_count,  # Use document count as score
                            }
                        )
            except Exception as e:
                logger.warning(f"Brand aggregation failed: {e}")

            # Sort by score and limit
            suggestions.sort(key=lambda x: x.get("score", 0), reverse=True)

            return Response({"suggestions": suggestions[:10]})

        except Exception as e:
            logger.error(f"Autocomplete search failed: {str(e)}", exc_info=True)
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
            # Check if your mapping has category_slug field, otherwise use category_name
            search = search.filter(
                "term",
                **{"category_name.keyword": category_slug.replace("-", " ").title()},
            )

        if brand_slug:
            # Fix: Use brand_name.keyword instead of brand_name__raw
            search = search.filter(
                "term", **{"brand_name.keyword": brand_slug.replace("-", " ").title()}
            )

        if location:
            search = search.filter("term", **{"location.keyword": location})

        # Sort by available fields only (choose one of these options)

        search = search.sort(
            "-is_featured",  # Featured products first
            "-popularity_score",  # Then by popularity
            "-average_rating",  # Then by rating
            "-created_at",  # Finally by recency
        )

        # Limit results for SEO pages
        search = search[:50]

        try:
            response = search.execute()

            # Use serializer for consistent data format
            serializer = ProductSearchListSerializer(response.hits, many=True)

            return Response(
                {
                    "results": serializer.data,
                    "total": (
                        response.hits.total.value
                        if hasattr(response.hits.total, "value")
                        else response.hits.total
                    ),
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

            # Add comprehensive aggregations
            search.aggs.bucket("avg_price", "avg", field="price")
            search.aggs.bucket("price_stats", "stats", field="price")

            # Check if these fields exist in your mapping
            if hasattr(ProductDocument, "category_id"):
                search.aggs.bucket(
                    "categories_count", "cardinality", field="category_id"
                )
            else:
                search.aggs.bucket(
                    "categories_count", "cardinality", field="category_name.keyword"
                )

            if hasattr(ProductDocument, "brand_id"):
                search.aggs.bucket("brands_count", "cardinality", field="brand_id")
            else:
                search.aggs.bucket(
                    "brands_count", "cardinality", field="brand_name.keyword"
                )

            search.aggs.bucket(
                "featured_count", "filter", filter={"term": {"is_featured": True}}
            )

            # Location stats
            search.aggs.bucket("locations", "terms", field="location.keyword", size=10)

            # Condition stats
            search.aggs.bucket(
                "conditions", "terms", field="condition_name.keyword", size=10
            )

            # Price ranges
            search.aggs.bucket(
                "price_ranges",
                "range",
                field="price",
                ranges=[
                    {"to": 100, "key": "under_100"},
                    {"from": 100, "to": 500, "key": "100_to_500"},
                    {"from": 500, "to": 1000, "key": "500_to_1000"},
                    {"from": 1000, "to": 5000, "key": "1000_to_5000"},
                    {"from": 5000, "key": "above_5000"},
                ],
            )

            # Top categories
            search.aggs.bucket(
                "top_categories", "terms", field="category_name.keyword", size=10
            )

            # Top brands
            search.aggs.bucket(
                "top_brands", "terms", field="brand_name.keyword", size=10
            )

            # Execute with no results, only aggregations
            search = search[:0]
            response = search.execute()

            # Get total count from the search response
            total_products = (
                response.hits.total.value
                if hasattr(response.hits.total, "value")
                else response.hits.total
            )

            stats = {
                "total_products": total_products,
                "average_price": round(response.aggregations.avg_price.value or 0, 2),
                "total_categories": response.aggregations.categories_count.value,
                "total_brands": response.aggregations.brands_count.value,
                "featured_products": response.aggregations.featured_count.doc_count,
                "price_stats": {
                    "min": response.aggregations.price_stats.min,
                    "max": response.aggregations.price_stats.max,
                    "avg": round(response.aggregations.price_stats.avg or 0, 2),
                    "sum": response.aggregations.price_stats.sum,
                    "count": response.aggregations.price_stats.count,
                },
                "price_ranges": {
                    bucket.key: bucket.doc_count
                    for bucket in response.aggregations.price_ranges.buckets
                },
                "top_categories": [
                    {"name": bucket.key, "count": bucket.doc_count}
                    for bucket in response.aggregations.top_categories.buckets
                ],
                "top_brands": [
                    {"name": bucket.key, "count": bucket.doc_count}
                    for bucket in response.aggregations.top_brands.buckets
                ],
                "top_locations": [
                    {"name": bucket.key, "count": bucket.doc_count}
                    for bucket in response.aggregations.locations.buckets
                ],
                "conditions": [
                    {"name": bucket.key, "count": bucket.doc_count}
                    for bucket in response.aggregations.conditions.buckets
                ],
            }

            return Response(stats)

        except Exception as e:
            logger.error(f"Stats retrieval failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Stats retrieval failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

from abc import ABC, abstractmethod
import logging
import time
from elasticsearch.dsl import Q
from elasticsearch import NotFoundError
from django.db import connections
from django.db.models import F

from apps.products.documents import ProductDocument
from apps.products.models import SearchLog, PopularSearch

logger = logging.getLogger(__name__)


class SearchQuery:
    """Data Transfer Object representing a search request."""

    def __init__(
        self,
        query_text: str = "",
        filters: dict = None,
        sort_by: str = "relevance",
        page: int = 1,
        page_size: int = 20,
        ip_address: str = "",
        user_agent: str = "",
        user=None,
    ):
        self.query_text = query_text
        self.filters = filters or {}
        self.sort_by = sort_by
        self.page = page
        self.page_size = page_size
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.user = user


class SearchResponse:
    """Data Transfer Object representing a search response."""

    def __init__(
        self,
        results,
        facets: dict,
        total_count: int,
        page: int,
        page_size: int,
        total_pages: int,
        query: str,
        took: int,
    ):
        self.results = results
        self.facets = facets
        self.total_count = total_count
        self.page = page
        self.page_size = page_size
        self.total_pages = total_pages
        self.query = query
        self.took = took


class SearchBackend(ABC):
    """Abstract interface defining the search backend capabilities."""

    @abstractmethod
    def query(
        self,
        query_text: str,
        filters: dict,
        sort_by: str,
        offset: int,
        limit: int,
    ) -> dict:
        """Execute a search query against the backend."""
        pass

    @abstractmethod
    def autocomplete(self, query_text: str, limit: int) -> list:
        """Fetch autocomplete suggestions for a given prefix."""
        pass

    @abstractmethod
    def find_related(self, product_id: str, limit: int) -> dict:
        """Find related products based on a reference product."""
        pass

    @abstractmethod
    def seo_search(
        self,
        category_slug: str,
        brand_slug: str,
        location: str,
        limit: int,
    ) -> dict:
        """Execute search optimized for SEO landing pages."""
        pass

    @abstractmethod
    def get_stats(self) -> dict:
        """Retrieve aggregated search performance metrics."""
        pass


class ElasticsearchSearchBackend(SearchBackend):
    """Elasticsearch-backed search adapter implementation."""

    def query(
        self,
        query_text: str,
        filters: dict,
        sort_by: str,
        offset: int,
        limit: int,
    ) -> dict:
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")

        # Full-text search
        if query_text:
            search_query = Q(
                "multi_match",
                query=query_text,
                fields=[
                    "title^3",
                    "brand_name^2",
                    "category_name^2",
                    "description^1",
                    "seo_keywords^2",
                    "search_text^1",
                ],
                type="best_fields",
                fuzziness="AUTO",
            )
            autocomplete_query = Q(
                "multi_match",
                query=query_text,
                fields=["title.autocomplete^2", "search_text.autocomplete^1"],
                type="phrase_prefix",
            )
            combined_query = Q("bool", should=[search_query, autocomplete_query])
            search = search.query(combined_query)

            logger.info(f"Applied Elasticsearch text search: {query_text}")

        # Apply range/price filters
        if filters.get("min_price"):
            search = search.filter("range", price={"gte": float(filters["min_price"])})
        if filters.get("max_price"):
            search = search.filter("range", price={"lte": float(filters["max_price"])})

        # Apply multi-value lists
        if filters.get("category"):
            categories = filters.getlist("category") if hasattr(filters, "getlist") else filters["category"]
            if not isinstance(categories, list):
                categories = [categories]
            search = search.filter("terms", category_slug=categories)

        if filters.get("brand"):
            brands = filters.getlist("brand") if hasattr(filters, "getlist") else filters["brand"]
            if not isinstance(brands, list):
                brands = [brands]
            search = search.filter("terms", brand_name__raw=brands)

        if filters.get("condition"):
            conditions = filters.getlist("condition") if hasattr(filters, "getlist") else filters["condition"]
            if not isinstance(conditions, list):
                conditions = [conditions]
            search = search.filter("terms", condition_name__raw=conditions)

        if filters.get("location"):
            search = search.filter("match", location=filters["location"])

        if filters.get("is_featured") == "true":
            search = search.filter("term", is_featured=True)
        if filters.get("is_negotiable") == "true":
            search = search.filter("term", is_negotiable=True)
        if filters.get("authenticity_guaranteed") == "true":
            search = search.filter("term", authenticity_guaranteed=True)

        if filters.get("min_rating"):
            search = search.filter(
                "range", average_rating={"gte": float(filters["min_rating"])}
            )

        # Apply sorting
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

        agg_search = search[:0]
        search = search[offset : offset + limit]

        response = search.execute()
        aggregations = self._get_aggregations(agg_search)

        return {
            "results": response,
            "aggregations": aggregations,
            "total_count": response.hits.total.value,
            "took": response.took,
        }

    def autocomplete(self, query_text: str, limit: int) -> list:
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")

        phrase_prefix_query = Q(
            "multi_match",
            query=query_text,
            fields=["title^3", "brand_name^2", "category_name^1"],
            type="phrase_prefix",
        )
        fuzzy_query = Q(
            "multi_match",
            query=query_text,
            fields=["title^1.5", "brand_name^1", "category_name^0.5"],
            fuzziness="AUTO",
        )
        combined_query = Q(
            "bool",
            should=[phrase_prefix_query, fuzzy_query],
            minimum_should_match=1,
        )
        search = search.query(combined_query)
        search = search.sort(
            {"_score": {"order": "desc"}}, {"popularity_score": {"order": "desc"}}
        )
        search = search[:limit]

        response = search.execute()
        suggestions = []
        seen_titles = set()
        seen_brands = set()

        for hit in response.hits:
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

            brand_name = getattr(hit, "brand_name", "")
            if (
                brand_name
                and brand_name.lower() not in seen_brands
                and query_text.lower() in brand_name.lower()
            ):
                seen_brands.add(brand_name.lower())
                suggestions.append(
                    {
                        "text": brand_name,
                        "type": "brand",
                        "score": hit.meta.score * 0.8,
                    }
                )

        # Additional brand aggregation suggestions
        brand_search = ProductDocument.search()
        brand_search = brand_search.filter("term", is_active=True)
        brand_search = brand_search.filter("term", status="active")
        brand_search = brand_search.query(
            "wildcard", **{"brand_name.keyword": f"{query_text}*"}
        )
        brand_search.aggs.bucket(
            "brands", "terms", field="brand_name.keyword", size=5
        )
        brand_search = brand_search[:0]

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
                            "score": bucket.doc_count,
                        }
                    )
        except Exception as e:
            logger.warning(f"Brand aggregation failed in autocomplete: {e}")

        suggestions.sort(key=lambda x: x.get("score", 0), reverse=True)
        return suggestions[:limit]

    def find_related(self, product_id: str, limit: int) -> dict:
        try:
            reference_product_doc = ProductDocument.get(id=product_id)
        except connections.get_connection().exceptions.NotFoundError:
            raise NotFoundError(
                f"Reference product with ID '{product_id}' not found in Elasticsearch."
            )

        reference_product_data = reference_product_doc.to_dict()
        all_should_queries = []
        debug_info = {"queries_added": []}

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
                minimum_should_match="10%",
                boost=4.0,
            )
            all_should_queries.append(mlt_query)
            debug_info["queries_added"].append(
                f"MLT query with fields: {mlt_fields}"
            )

        if category_id := reference_product_data.get("category_id"):
            all_should_queries.append(
                Q("term", category_id={"value": category_id, "boost": 2.5})
            )
            debug_info["queries_added"].append(f"Category ID: {category_id}")
        elif category_name := reference_product_data.get("category_name"):
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

        if brand_id := reference_product_data.get("brand_id"):
            all_should_queries.append(
                Q("term", brand_id={"value": brand_id, "boost": 2.0})
            )
            debug_info["queries_added"].append(f"Brand ID: {brand_id}")
        elif brand_name := reference_product_data.get("brand_name"):
            all_should_queries.append(
                Q(
                    "term",
                    **{"brand_name.keyword": {"value": brand_name, "boost": 2.0}},
                )
            )
            debug_info["queries_added"].append(f"Brand Name: {brand_name}")

        if condition_id := reference_product_data.get("condition_id"):
            all_should_queries.append(
                Q("term", condition_id={"value": condition_id, "boost": 1.5})
            )
            debug_info["queries_added"].append(f"Condition ID: {condition_id}")
        elif condition_name := reference_product_data.get("condition_name"):
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

        if title := reference_product_data.get("title"):
            all_should_queries.append(
                Q("term", **{"title.keyword": {"value": title, "boost": 3.0}})
            )
            debug_info["queries_added"].append(f"Exact Title: {title}")

        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")
        search = search.exclude("term", _id=product_id)

        if not all_should_queries:
            debug_info["error"] = "No should queries generated"
            return {
                "related_products": [],
                "total_count": 0,
                "debug_info": debug_info,
            }

        final_query = Q(
            "bool", should=all_should_queries, minimum_should_match=1
        )
        search = search.query(final_query)
        search = search.sort(
            {"_score": {"order": "desc"}}, {"popularity_score": {"order": "desc"}}
        )
        search = search[:limit]

        response = search.execute()
        return {
            "results": response.hits,
            "total_count": (
                response.hits.total.value
                if hasattr(response.hits.total, "value")
                else response.hits.total
            ),
            "debug_info": debug_info,
        }

    def seo_search(
        self,
        category_slug: str,
        brand_slug: str,
        location: str,
        limit: int,
    ) -> dict:
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")

        if category_slug:
            search = search.filter(
                "term",
                **{
                    "category_name.keyword": category_slug.replace(
                        "-", " "
                    ).title()
                },
            )

        if brand_slug:
            search = search.filter(
                "term",
                **{"brand_name.keyword": brand_slug.replace("-", " ").title()},
            )

        if location:
            search = search.filter("term", **{"location.keyword": location})

        search = search.sort(
            "-is_featured",
            "-popularity_score",
            "-average_rating",
            "-created_at",
        )
        search = search[:limit]

        response = search.execute()
        return {
            "results": response.hits,
            "total_count": (
                response.hits.total.value
                if hasattr(response.hits.total, "value")
                else response.hits.total
            ),
        }

    def get_stats(self) -> dict:
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)

        search.aggs.bucket("avg_price", "avg", field="price")
        search.aggs.bucket("price_stats", "stats", field="price")

        if hasattr(ProductDocument, "category_id"):
            search.aggs.bucket(
                "categories_count", "cardinality", field="category_id"
            )
        else:
            search.aggs.bucket(
                "categories_count",
                "cardinality",
                field="category_name.keyword",
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
        search.aggs.bucket(
            "locations", "terms", field="location.keyword", size=10
        )
        search.aggs.bucket(
            "conditions", "terms", field="condition_name.keyword", size=10
        )

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

        search.aggs.bucket(
            "top_categories", "terms", field="category_name.keyword", size=10
        )
        search.aggs.bucket(
            "top_brands", "terms", field="brand_name.keyword", size=10
        )

        search = search[:0]
        response = search.execute()

        total_products = (
            response.hits.total.value
            if hasattr(response.hits.total, "value")
            else response.hits.total
        )

        return {
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

    def _get_aggregations(self, search):
        try:
            search.aggs.bucket("brands", "terms", field="brand_name.raw", size=20)
            search.aggs.bucket(
                "categories", "terms", field="category_name.raw", size=20
            )
            search.aggs.bucket(
                "conditions", "terms", field="condition_name.raw", size=10
            )
            search.aggs.bucket(
                "locations", "terms", field="location.raw", size=20
            )

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
                    {"key": loc.key, "count": loc.doc_count}
                    for loc in agg_response.aggregations.locations.buckets
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


class SearchCoordinator:
    """Orchestrates search queries and logs analytics."""

    def __init__(self, backend: SearchBackend = None):
        self.backend = backend or ElasticsearchSearchBackend()

    def execute_search(self, query: SearchQuery) -> SearchResponse:
        start_time = time.time()
        offset = (query.page - 1) * query.page_size

        # Fetch results from backend
        data = self.backend.query(
            query_text=query.query_text,
            filters=query.filters,
            sort_by=query.sort_by,
            offset=offset,
            limit=query.page_size,
        )

        took_time = time.time() - start_time

        total_count = data["total_count"]
        total_pages = (total_count + query.page_size - 1) // query.page_size

        # Record analytics log (SearchLog + PopularSearch)
        if query.query_text:
            try:
                SearchLog.objects.create(
                    user=query.user if query.user and query.user.is_authenticated else None,
                    query=query.query_text,
                    filters=dict(query.filters.items()) if hasattr(query.filters, "items") else query.filters,
                    results_count=total_count,
                    ip_address=query.ip_address or None,
                    user_agent=query.user_agent or "",
                    response_time=took_time,
                )

                popular_search, created = PopularSearch.objects.get_or_create(
                    query=query.query_text, defaults={"search_count": 1}
                )
                if not created:
                    popular_search.search_count = F("search_count") + 1
                    popular_search.save(update_fields=["search_count"])
            except Exception as e:
                logger.error(f"Failed to save search analytics log: {e}")

        return SearchResponse(
            results=data["results"],
            facets=data["aggregations"],
            total_count=total_count,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
            query=query.query_text,
            took=data["took"],
        )

    def execute_autocomplete(self, query_text: str, limit: int = 10) -> list:
        return self.backend.autocomplete(query_text=query_text, limit=limit)

    def execute_find_related(self, product_id: str, limit: int = 20) -> dict:
        return self.backend.find_related(product_id=product_id, limit=limit)

    def execute_seo_search(
        self,
        category_slug: str,
        brand_slug: str,
        location: str,
        limit: int = 50,
    ) -> dict:
        return self.backend.seo_search(
            category_slug=category_slug,
            brand_slug=brand_slug,
            location=location,
            limit=limit,
        )

    def execute_get_stats(self) -> dict:
        return self.backend.get_stats()

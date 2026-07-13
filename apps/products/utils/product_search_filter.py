from django.db.models import Q


class ProductSearchFilters:
    """Advanced search filters for complex queries"""

    @staticmethod
    def apply_advanced_filters(search, filters):
        """Apply advanced filters to search query"""

        # Date range filters
        if filters.get("created_after"):
            search = search.filter(
                "range", created_at={"gte": filters["created_after"]}
            )

        if filters.get("created_before"):
            search = search.filter(
                "range", created_at={"lte": filters["created_before"]}
            )

        # Multiple category filter with OR logic
        if filters.get("categories"):
            category_queries = [
                Q("term", category_slug=cat) for cat in filters["categories"]
            ]
            search = search.query(Q("bool", should=category_queries))

        # Price range with currency consideration
        if filters.get("price_range"):
            price_filter = filters["price_range"]
            if price_filter.get("min") or price_filter.get("max"):
                range_filter = {}
                if price_filter.get("min"):
                    range_filter["gte"] = price_filter["min"]
                if price_filter.get("max"):
                    range_filter["lte"] = price_filter["max"]
                search = search.filter("range", price=range_filter)

        # Advanced text search with field boosting
        if filters.get("advanced_query"):
            query_data = filters["advanced_query"]

            must_queries = []
            should_queries = []

            if query_data.get("title"):
                must_queries.append(Q("match", title=query_data["title"]))

            if query_data.get("description"):
                should_queries.append(Q("match", description=query_data["description"]))

            if query_data.get("brand"):
                must_queries.append(Q("term", brand_name__raw=query_data["brand"]))

            if query_data.get("any_field"):
                should_queries.append(
                    Q(
                        "multi_match",
                        query=query_data["any_field"],
                        fields=["title^2", "description", "search_text"],
                    )
                )

            if must_queries or should_queries:
                bool_query = Q("bool")
                if must_queries:
                    bool_query = bool_query.must(must_queries)
                if should_queries:
                    bool_query = bool_query.should(should_queries)

                search = search.query(bool_query)

        # Exclude certain conditions
        if filters.get("exclude_conditions"):
            for condition in filters["exclude_conditions"]:
                search = search.exclude("term", condition_name__raw=condition)

        # Geolocation-based search (if you have coordinates)
        if filters.get("near_location"):
            location_data = filters["near_location"]
            if location_data.get("lat") and location_data.get("lon"):
                search = search.filter(
                    "geo_distance",
                    distance=location_data.get("distance", "50km"),
                    location={"lat": location_data["lat"], "lon": location_data["lon"]},
                )

        return search

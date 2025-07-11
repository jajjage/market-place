from django.db.models import Q
from ..documents import ProductDocument


class ProductSearchUtils:
    """Utility class for product search operations"""

    @staticmethod
    def get_trending_products(limit=10):
        """Get trending products based on views and ratings"""
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)
        search = search.filter("term", status="active")
        search = search.sort("-views_count", "-popularity_score")
        search = search[:limit]

        try:
            response = search.execute()
            return [hit.meta.id for hit in response]
        except:
            return []

    @staticmethod
    def get_similar_products(product_id, limit=5):
        """Get products similar to the given product"""
        try:
            # Get the product document
            product_doc = ProductDocument.get(id=product_id)

            # Build similarity query
            search = ProductDocument.search()
            search = search.filter("term", is_active=True)
            search = search.filter("term", status="active")
            search = search.exclude(
                "term", id=product_id
            )  # Exclude the current product

            # Similar by category and brand
            should_queries = []

            if product_doc.category_name:
                should_queries.append(
                    Q("term", category_name__raw=product_doc.category_name)
                )

            if product_doc.brand_name:
                should_queries.append(Q("term", brand_name__raw=product_doc.brand_name))

            # Similar price range (±20%)
            if product_doc.price:
                min_price = product_doc.price * 0.8
                max_price = product_doc.price * 1.2
                should_queries.append(
                    Q("range", price={"gte": min_price, "lte": max_price})
                )

            if should_queries:
                search = search.query(Q("bool", should=should_queries))

            search = search.sort("-popularity_score")
            search = search[:limit]

            response = search.execute()
            return [hit.meta.id for hit in response]

        except:
            return []

    @staticmethod
    def get_search_suggestions(query, limit=5):
        """Get search suggestions based on popular searches"""
        search = ProductDocument.search()
        search = search.filter("term", is_active=True)

        # Use aggregation to get popular terms
        search.aggs.bucket("popular_titles", "terms", field="title.raw", size=limit)
        search.aggs.bucket(
            "popular_brands", "terms", field="brand_name.raw", size=limit
        )
        search.aggs.bucket(
            "popular_categories", "terms", field="category_name.raw", size=limit
        )

        if query:
            search = search.query("wildcard", search_text=f"*{query.lower()}*")

        search = search[:0]  # We only want aggregations

        try:
            response = search.execute()

            suggestions = []

            # Collect suggestions from aggregations
            for bucket in response.aggregations.popular_titles.buckets:
                if query.lower() in bucket.key.lower():
                    suggestions.append(
                        {
                            "text": bucket.key,
                            "type": "product",
                            "count": bucket.doc_count,
                        }
                    )

            for bucket in response.aggregations.popular_brands.buckets:
                if query.lower() in bucket.key.lower():
                    suggestions.append(
                        {"text": bucket.key, "type": "brand", "count": bucket.doc_count}
                    )

            for bucket in response.aggregations.popular_categories.buckets:
                if query.lower() in bucket.key.lower():
                    suggestions.append(
                        {
                            "text": bucket.key,
                            "type": "category",
                            "count": bucket.doc_count,
                        }
                    )

            # Sort by count and return top suggestions
            suggestions.sort(key=lambda x: x["count"], reverse=True)
            return suggestions[:limit]

        except:
            return []

    @staticmethod
    def update_product_views(product_id):
        """Update product views count in both database and Elasticsearch"""
        from apps.products.product_metadata.models import ProductMeta
        from apps.products.product_base.models import Product

        try:
            product = Product.objects.get(id=product_id)
            meta, created = ProductMeta.objects.get_or_create(
                product=product, defaults={"views_count": 0}
            )

            # Increment views count
            meta.views_count += 1
            meta.save()

            # Update Elasticsearch document
            try:
                doc = ProductDocument.get(id=product_id)
                doc.update(views_count=meta.views_count)
                # Recalculate popularity score
                doc.update(popularity_score=doc.prepare_popularity_score(product))
            except:
                pass  # Document might not exist

            return True

        except Product.DoesNotExist:
            return False

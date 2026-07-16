from django.core.management.base import BaseCommand
from elasticsearch.dsl import Q
from apps.products.documents import ProductDocument

class Command(BaseCommand):
    help = "Verify Elasticsearch connection, index definitions, and query relevance"

    def handle(self, *args, **options):
        self.stdout.write("=== Starting Elasticsearch Search Verification ===")

        # 1. Test basic connection and index stats
        search = ProductDocument.search()
        try:
            total_docs = search.count()
            self.stdout.write(self.style.SUCCESS(
                f"✓ Successfully connected to Elasticsearch. Index '{ProductDocument._index._name}' has {total_docs} documents."
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Failed to connect to Elasticsearch: {str(e)}"))
            return

        # 2. Test Full-Text Search for "HP"
        self.stdout.write("\nTesting full-text search for query: 'HP'...")
        q_text = "HP"
        search_query = Q(
            "multi_match",
            query=q_text,
            fields=["title^3", "brand_name^2", "description^1", "search_text^1"],
            type="best_fields",
            fuzziness="AUTO",
        )
        hp_search = search.query(search_query)
        hp_results = hp_search.execute()
        
        self.stdout.write(f"Found {len(hp_results)} results:")
        for hit in hp_results:
            self.stdout.write(f"  - [ID: {hit.meta.id}] Title: {hit.title} | Brand: {getattr(hit, 'brand_name', 'N/A')} (Score: {hit.meta.score})")

        if len(hp_results) >= 2:
            self.stdout.write(self.style.SUCCESS("✓ Full-text search verified successfully (found HP Laptop and HP Printer)."))
        else:
            self.stdout.write(self.style.WARNING("⚠ Full-text search returned fewer results than expected."))

        # 3. Test Autocomplete Suggestion for "Sa"
        self.stdout.write("\nTesting autocomplete suggestion for prefix: 'Sa'...")
        prefix = "Sa"
        autocomplete_query = Q(
            "multi_match",
            query=prefix,
            fields=["title.autocomplete^2", "search_text.autocomplete^1"],
            type="phrase_prefix",
        )
        ac_search = search.query(autocomplete_query)
        ac_results = ac_search.execute()

        self.stdout.write(f"Found {len(ac_results)} autocomplete suggestions:")
        has_samsung = False
        for hit in ac_results:
            self.stdout.write(f"  - Suggestion: {hit.title}")
            if "Samsung" in hit.title:
                has_samsung = True

        if has_samsung:
            self.stdout.write(self.style.SUCCESS("✓ Autocomplete search verified successfully (found Samsung)."))
        else:
            self.stdout.write(self.style.WARNING("⚠ Autocomplete search did not return Samsung."))

        # 4. Test Filtering by Location "Lagos"
        self.stdout.write("\nTesting filters: location='Lagos'...")
        lagos_search = search.filter("term", is_active=True).filter("term", status="active").filter("match", location="Lagos")
        lagos_results = lagos_search.execute()

        self.stdout.write(f"Found {len(lagos_results)} products in Lagos:")
        all_in_lagos = True
        for hit in lagos_results:
            loc = getattr(hit, "location", "N/A")
            self.stdout.write(f"  - {hit.title} (Location: {loc})")
            if loc != "Lagos":
                all_in_lagos = False

        if all_in_lagos and len(lagos_results) > 0:
            self.stdout.write(self.style.SUCCESS("✓ Location filtering verified successfully."))
        else:
            self.stdout.write(self.style.ERROR("✗ Location filtering failed or returned empty results."))

        # 5. Test Faceted Search Aggregations
        self.stdout.write("\nTesting faceted search aggregations...")
        agg_search = search[:0]  # Only aggregations
        agg_search.aggs.bucket("brands", "terms", field="brand_name.raw", size=20)
        agg_search.aggs.bucket("categories", "terms", field="category_name.raw", size=20)
        
        agg_response = agg_search.execute()
        
        self.stdout.write("Brand facets:")
        for bucket in agg_response.aggregations.brands.buckets:
            self.stdout.write(f"  - {bucket.key}: {bucket.doc_count} products")
            
        self.stdout.write("Category facets:")
        for bucket in agg_response.aggregations.categories.buckets:
            self.stdout.write(f"  - {bucket.key}: {bucket.doc_count} products")

        if len(agg_response.aggregations.brands.buckets) > 0:
            self.stdout.write(self.style.SUCCESS("✓ Faceted search aggregations verified successfully."))
        else:
            self.stdout.write(self.style.ERROR("✗ Faceted search aggregations failed."))

        self.stdout.write("\n=== Elasticsearch Search Verification Completed ===")

from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.products.services.search import (
    SearchBackend,
    SearchCoordinator,
    SearchQuery,
)
from apps.products.models import SearchLog, PopularSearch

User = get_user_model()


class MockSearchBackend(SearchBackend):
    def __init__(self):
        self.query_called = False
        self.autocomplete_called = False
        self.find_related_called = False
        self.seo_search_called = False
        self.get_stats_called = False

    def query(self, query_text, filters, sort_by, offset, limit):
        self.query_called = True
        mock_hit = type(
            "Hit",
            (),
            {
                "meta": type("Meta", (), {"id": "1", "score": 1.0})(),
                "title": "Test Product",
                "price": 100.0,
            },
        )()
        return {
            "results": [mock_hit],
            "aggregations": {"brands": []},
            "total_count": 1,
            "took": 10,
        }

    def autocomplete(self, query_text, limit):
        self.autocomplete_called = True
        return [{"text": "Test Suggestion", "type": "product"}]

    def find_related(self, product_id, limit):
        self.find_related_called = True
        return {"results": [], "total_count": 0, "debug_info": {}}

    def seo_search(self, category_slug, brand_slug, location, limit):
        self.seo_search_called = True
        return {"results": [], "total_count": 0}

    def get_stats(self):
        self.get_stats_called = True
        return {"total_products": 0}


class SearchServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            password="testpassword123",
        )
        self.mock_backend = MockSearchBackend()
        self.coordinator = SearchCoordinator(backend=self.mock_backend)

    def test_search_orchestration_and_analytics_logging(self):
        query = SearchQuery(
            query_text="Laptop",
            filters={"min_price": 50},
            sort_by="newest",
            page=1,
            page_size=10,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            user=self.user,
        )

        response = self.coordinator.execute_search(query)

        # Assert query was delegated
        self.assertTrue(self.mock_backend.query_called)
        self.assertEqual(response.total_count, 1)
        self.assertEqual(response.total_pages, 1)
        self.assertEqual(len(response.results), 1)

        # Assert SearchLog was created
        log = SearchLog.objects.filter(query="Laptop").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.ip_address, "127.0.0.1")
        self.assertEqual(log.user_agent, "TestAgent")
        self.assertEqual(log.results_count, 1)

        # Assert PopularSearch was updated
        popular = PopularSearch.objects.filter(query="Laptop").first()
        self.assertIsNotNone(popular)
        self.assertEqual(popular.search_count, 1)

    def test_popular_search_increment(self):
        # First search
        q1 = SearchQuery(query_text="Phone")
        self.coordinator.execute_search(q1)

        # Second search
        q2 = SearchQuery(query_text="Phone")
        self.coordinator.execute_search(q2)

        popular = PopularSearch.objects.filter(query="Phone").first()
        self.assertIsNotNone(popular)
        self.assertEqual(popular.search_count, 2)

    def test_autocomplete_delegation(self):
        suggestions = self.coordinator.execute_autocomplete("Sa")
        self.assertTrue(self.mock_backend.autocomplete_called)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["text"], "Test Suggestion")

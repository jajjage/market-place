import time
import json
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve
from django.db.models import F
from .models import SearchLog, PopularSearch


class SearchAnalyticsMiddleware(MiddlewareMixin):
    """Middleware to track search analytics"""

    def process_request(self, request):
        # Start timing the request
        request._search_start_time = time.time()
        return None

    def process_response(self, request, response):
        # Only track search endpoints
        if not self._is_search_endpoint(request):
            return response

        # Calculate response time
        response_time = time.time() - getattr(
            request, "_search_start_time", time.time()
        )

        # Extract search parameters
        search_data = self._extract_search_data(request)

        if search_data:
            # Log the search
            self._log_search(request, response, search_data, response_time)

            # Update popular searches
            self._update_popular_searches(search_data.get("query", ""))

        return response

    def _is_search_endpoint(self, request):
        """Check if the request is for a search endpoint"""
        try:
            resolver_match = resolve(request.path_info)
            return resolver_match.url_name in [
                "product-search",
                "product-autocomplete",
                "product-seo-search",
            ]
        except:
            return False

    def _extract_search_data(self, request):
        """Extract search data from request"""
        if request.method == "GET":
            query = request.GET.get("q", "").strip()
            if not query:
                return None

            return {
                "query": query,
                "filters": dict(request.GET.items()),
                "method": "GET",
            }

        elif request.method == "POST" and hasattr(request, "data"):
            query = request.data.get("q", "").strip()
            if not query:
                return None

            return {
                "query": query,
                "filters": dict(request.data.items()),
                "method": "POST",
            }

        return None

    def _log_search(self, request, response, search_data, response_time):
        """Log the search query"""
        try:
            # Extract results count from response
            results_count = 0
            if response.status_code == 200:
                try:
                    response_data = json.loads(response.content.decode("utf-8"))
                    results_count = response_data.get("total", 0)
                except:
                    pass

            # Create search log entry
            SearchLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                query=search_data["query"],
                filters=search_data["filters"],
                results_count=results_count,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                response_time=response_time,
            )

        except Exception as e:
            # Don't let analytics errors break the request
            pass

    def _update_popular_searches(self, query):
        """Update popular searches"""
        if not query:
            return

        try:
            popular_search, created = PopularSearch.objects.get_or_create(
                query=query, defaults={"search_count": 1}
            )

            if not created:
                popular_search.search_count = F("search_count") + 1
                popular_search.save(update_fields=["search_count"])

        except Exception as e:
            # Don't let analytics errors break the request
            pass

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

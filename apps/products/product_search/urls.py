from django.urls import path
from .views import (
    ProductSearchView,
    ProductRelatedSearchView,
    ProductAutocompleteView,
    ProductSEOSearchView,
    ProductSearchStatsView,
    ElasticsearchDebugView,  # Add this debug view
)

urlpatterns = [
    # Main search endpoint
    path("search/", ProductSearchView.as_view(), name="product-search"),
    # Related products
    path(
        "search/related/<int:product_id>/",
        ProductRelatedSearchView.as_view(),
        name="product-related-search",
    ),
    # Autocomplete
    path(
        "search/autocomplete/",
        ProductAutocompleteView.as_view(),
        name="product-autocomplete",
    ),
    # SEO search
    path("search/seo/", ProductSEOSearchView.as_view(), name="product-seo-search"),
    # Search statistics
    path(
        "search/stats/", ProductSearchStatsView.as_view(), name="product-search-stats"
    ),
    # Debug endpoint - remove in production
    path("search/debug/", ElasticsearchDebugView.as_view(), name="elasticsearch-debug"),
]

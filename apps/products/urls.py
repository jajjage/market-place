from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.products.views import *

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"brands", BrandViewSet, basename="brands")
router.register(r"brand-requests", BrandRequestViewSet, basename="brand-requests")
router.register(
    r"brand-variant-templates",
    BrandVariantTemplateViewSet,
    basename="brand-variant-template",
)
router.register(r"brand-variants", BrandVariantViewSet, basename="brand-variants")
router.register(r"conditions", ProductConditionViewSet, basename="product-condition")
router.register(
    r"detail-templates",
    ProductDetailTemplateViewSet,
    basename="detail-template",
)
router.register(
    r"product-details/(?P<product_pk>[0-9a-f-]+)",
    ProductDetailViewSet,
    basename="product-detail",
)
router.register(r"images", ProductImageViewSet, basename="product-image")
router.register(
    r"image-variants",
    ProductImageVariantViewSet,
    basename="product-image-variant",
)
router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(r"product-metadata", ProductMetaViewSet, basename="product-metadata")
router.register(r"negotiations", ProductNegotiationViewSet, basename="negotiation")
router.register(r"ratings", ProductRatingViewSet, basename="product-rating")
router.register(r"variants", ProductVariantViewSet, basename="variant")
router.register(r"variant-types", ProductVariantTypeViewSet, basename="variant-type")
router.register(
    r"variant-options",
    ProductVariantOptionViewSet,
    basename="variant-option",
)
router.register(r"watchlists", ProductWatchlistViewSet, basename="watchlist")

urlpatterns = [
    path("brand-search/", BrandSearchView.as_view(), name="brand-search"),
    path(
        "products-short-code/<str:short_code>/",
        ProductDetailByShortCode.as_view(),
        name="product-detail-by-shortcode",
    ),
    path("conditions/dropdown/", ProductConditionViewSet.as_view({"get": "active"}), name="conditions-dropdown"),
    path(
        "conditions/quality/<int:score>/",
        ProductConditionViewSet.as_view({"get": "by_quality"}),
        name="conditions-by-quality",
    ),
    path("search/", ProductSearchView.as_view(), name="product-search"),
    path(
        "search/related/<uuid:product_id>/",
        ProductRelatedSearchView.as_view(),
        name="product-related-search",
    ),
    path(
        "search/autocomplete/",
        ProductAutocompleteView.as_view(),
        name="product-autocomplete",
    ),
    path("search/seo/", ProductSEOSearchView.as_view(), name="product-seo-search"),
    path("search/stats/", ProductSearchStatsView.as_view(), name="product-search-stats"),
    path("search/debug/", ElasticsearchDebugView.as_view(), name="elasticsearch-debug"),
    path("", include(router.urls)),
]

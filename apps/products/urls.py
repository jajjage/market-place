from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet,
    CategoryViewSet,
    ProductDetailByShortCode,
    ProductConditionViewSet,
    ProductImageViewSet,
    ProductWatchlistViewSet,
    ProductMetaViewSet,
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"conditions", ProductConditionViewSet, basename="condition")
router.register(r"images", ProductImageViewSet, basename="image")
router.register(r"metadata", ProductMetaViewSet, basename="metadata")
router.register(r"watchlist", ProductWatchlistViewSet, basename="watchlist")

# The API URLs are determined automatically by the router
urlpatterns = [
    path(
        "products-short-code/<str:short_code>/",
        ProductDetailByShortCode.as_view(),
        name="product-detail-by-shortcode",
    ),
    path("", include(router.urls)),
    # Custom product retrieval endpoints for social sharing
]

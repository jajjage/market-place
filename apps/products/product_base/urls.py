from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet,
    ProductDetailByShortCode,
)

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")


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

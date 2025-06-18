from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductMetaViewSet

router = DefaultRouter()

# Metadata management endpoints
router.register(r"product-metadata", ProductMetaViewSet, basename="product-metadata")

urlpatterns = [
    path("", include(router.urls)),
]

# This creates the following URL structure:
#
# PRODUCT ENDPOINTS:
# GET    /api/v1/products/{id}/with-seo/       - Get product with SEO metadata
# GET    /api/v1/products/{id}/manage-metadata/ - Get metadata for owned product
# PATCH  /api/v1/products/{id}/manage-metadata/ - Update metadata for owned product
#
# ANALYTICS ENDPOINTS:
# POST   /api/v1/product-analytics/{id}/track-view/ - Track product view (async)
#
# METADATA ENDPOINTS (Public & Admin):
# GET    /api/v1/product-metadata/              - List all metadata (admin)
# GET    /api/v1/product-metadata/stats/        - Get metadata statistics
# GET    /api/v1/product-metadata/featured/     - Get featured products metadata
# GET    /api/v1/product-metadata/popular/      - Get popular products metadata
# GET    /api/v1/product-metadata/by-product/   - Get metadata by product ID/slug
# GET    /api/v1/product-metadata/my-products/  - Get my products metadata (authenticated)
# PATCH  /api/v1/product-metadata/update-my-product/ - Update my product metadata

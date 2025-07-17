from django.urls import path, include
from rest_framework_nested import routers

from rest_framework.routers import DefaultRouter
from .views import (
    BrandVariantViewSet,
    BrandViewSet,
    BrandRequestViewSet,
    BrandSearchView,
)

router = DefaultRouter()
router.register(r"brands", BrandViewSet, basename="brands")
router.register(r"brand-requests", BrandRequestViewSet, basename="brand-requests")

# Nested router for variants
brands_router = routers.NestedDefaultRouter(router, r"brands", lookup="brand")
brands_router.register(r"variants", BrandVariantViewSet, basename="brand-variants")


urlpatterns = [
    path("brand-search/", BrandSearchView.as_view(), name="brand-search"),
    path("", include(router.urls)),
    path("", include(brands_router.urls)),
]

from django.urls import path, include

from rest_framework.routers import DefaultRouter
from .views import (
    BrandVariantTemplateViewSet,
    BrandVariantViewSet,
    BrandViewSet,
    BrandRequestViewSet,
    BrandSearchView,
)

router = DefaultRouter()
router.register(r"brands", BrandViewSet, basename="brands")
router.register(r"brand-requests", BrandRequestViewSet, basename="brand-requests")
router.register(
    r"brand-variant-templates",
    BrandVariantTemplateViewSet,
    basename="brand-variant-template",
)
router.register(r"brand-variants", BrandVariantViewSet, basename="brand-variants")

urlpatterns = [
    path("brand-search/", BrandSearchView.as_view(), name="brand-search"),
    path("", include(router.urls)),
]

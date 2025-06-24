from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductVariantViewSet,
    ProductVariantTypeViewSet,
    ProductVariantOptionViewSet,
)


router = DefaultRouter()
router.register(r"variants", ProductVariantViewSet, basename="variant")
router.register(r"variant-types", ProductVariantTypeViewSet, basename="variant-type")
router.register(
    r"variant-options", ProductVariantOptionViewSet, basename="variant-option"
)

urlpatterns = [
    path("", include(router.urls)),
    # Alternative endpoints for specific use cases
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductVariantViewSet, ProductVariantTypeViewSet


router = DefaultRouter()
router.register(r"variants", ProductVariantViewSet, basename="variant")

urlpatterns = [
    path("", include(router.urls)),
    # Alternative endpoints for specific use cases
    path(
        "product-variant-type/",
        ProductVariantTypeViewSet.as_view({"get": "list"}),
        name="product-variant-type-list",
    ),
]

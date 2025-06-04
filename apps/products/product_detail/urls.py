from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductDetailViewSet, ProductDetailTemplateViewSet

# Main router
router = DefaultRouter()
router.register(
    r"product-detail-templates",
    ProductDetailTemplateViewSet,
    basename="product-detail-template",
)

router.register(r"details", ProductDetailViewSet, basename="product-details")

urlpatterns = [
    path("", include(router.urls)),
    # Additional standalone endpoints
    path(
        "api/product-details/",
        ProductDetailViewSet.as_view({"get": "list", "post": "create"}),
        name="product-detail-standalone-list",
    ),
]

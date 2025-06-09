from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductDetailViewSet, ProductDetailTemplateViewSet

# Main router
router = DefaultRouter()
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
urlpatterns = [
    path("", include(router.urls)),
]

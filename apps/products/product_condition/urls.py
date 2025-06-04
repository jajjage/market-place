from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductConditionViewSet


router = DefaultRouter()
router.register(r"conditions", ProductConditionViewSet, basename="product-condition")

urlpatterns = [
    path("", include(router.urls)),
    # Alternative endpoints for specific use cases
    path(
        "conditions/dropdown/",
        ProductConditionViewSet.as_view({"get": "active"}),
        name="conditions-dropdown",
    ),
    path(
        "conditions/quality/<int:score>/",
        ProductConditionViewSet.as_view({"get": "by_quality"}),
        name="conditions-by-quality",
    ),
]

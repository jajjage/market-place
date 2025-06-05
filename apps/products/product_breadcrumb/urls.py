# your_project_name/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter


# Your newly created BreadcrumbViewSet
from apps.products.product_breadcrumb.views import (
    BreadcrumbViewSet,
)  # Adjust path if moved to apps/breadcrumbs/

router = DefaultRouter()
router.register(
    r"breadcrumbs", BreadcrumbViewSet, basename="breadcrumb"
)  # Register the Breadcrumb ViewSet

urlpatterns = [
    path("", include(router.urls)),
]

from django.urls import include, path
from .views import CategoryViewSet, CategoryAdminViewSet

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"admin-categories", CategoryAdminViewSet, basename="admin-category")

urlpatterns = [
    path("", include(router.urls)),
]

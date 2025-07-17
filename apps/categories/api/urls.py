from django.urls import include, path
from .views import CategoryViewSet, CategoryAdminViewSet, CategorySearchView

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"admin-categories", CategoryAdminViewSet, basename="admin-category")

urlpatterns = [
    path("category-search/", CategorySearchView.as_view(), name="category-search"),
    path("", include(router.urls)),
]

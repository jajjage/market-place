from django.urls import include, path
from .views import (
    CategoryViewSet,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
]

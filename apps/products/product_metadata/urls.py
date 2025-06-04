from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductMetaViewSet

router = DefaultRouter()
router.register(r"metadata", ProductMetaViewSet, basename="metadata")

urlpatterns = [
    path("", include(router.urls)),
    # Custom product retrieval endpoints for social sharing
]

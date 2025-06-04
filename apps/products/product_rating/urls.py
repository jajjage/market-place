from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductRatingViewSet


router = DefaultRouter()
router.register(r"ratings", ProductRatingViewSet, basename="rating")

urlpatterns = [
    path("", include(router.urls)),
    # Alternative endpoints for specific use cases
]

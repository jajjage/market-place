from django.urls import include, path
from .views import (
    RatingViewSet,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"ratings", RatingViewSet, basename="user-rating")

urlpatterns = [
    path("", include(router.urls)),
]

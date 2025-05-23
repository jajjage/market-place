from django.urls import include, path
from .views import (
    UserRatingViewSet,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"users/rating", UserRatingViewSet, basename="user-rating")

urlpatterns = [
    path("", include(router.urls)),
]

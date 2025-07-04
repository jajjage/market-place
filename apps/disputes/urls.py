from django.urls import include, path
from .views import (
    DisputeViewSet,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"disputes", DisputeViewSet, basename="user-dispute")

urlpatterns = [
    path("", include(router.urls)),
]

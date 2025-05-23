from django.urls import include, path
from .views import (
    UserStoreViewSet,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"users/stores", UserStoreViewSet, basename="user-store")

urlpatterns = [
    path("", include(router.urls)),
]

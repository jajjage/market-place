from django.urls import include, path
from apps.users.views import (
    UserAddressViewSet,
    UserProfileViewSet,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"users/addresses", UserAddressViewSet, basename="user-address")
router.register(r"users/profiles", UserProfileViewSet, basename="user-profile")

urlpatterns = [
    path("", include(router.urls)),
]

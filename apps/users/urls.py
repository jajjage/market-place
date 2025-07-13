from django.urls import include, path
from apps.users.views import (
    UserAddressViewSet,
    UserProfileViewSet,
    buyer_analytics_view,
    seller_analytics_view,
)

from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# Register our custom viewsets
router.register(r"users/addresses", UserAddressViewSet, basename="user-address")
router.register(r"users/profiles", UserProfileViewSet, basename="user-profile")

urlpatterns = [
    path("", include(router.urls)),
    path("seller/analytics/", seller_analytics_view, name="seller-analytics"),
    path("buyer/analytics/", buyer_analytics_view, name="buyer-analytics"),
]

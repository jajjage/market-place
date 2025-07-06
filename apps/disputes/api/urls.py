from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.disputes.api.views import DisputeViewSet

router = DefaultRouter()
router.register(r"disputes", DisputeViewSet, basename="user-dispute")

urlpatterns = [
    path("", include(router.urls)),
]

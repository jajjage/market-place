from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EscrowTransactionViewSet

router = DefaultRouter()
router.register(r"transactions", EscrowTransactionViewSet, basename="transactions")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "transactions/<uuid:id>/", EscrowTransactionViewSet.as_view({"get": "retrieve"})
    ),
    path(
        "transactions/track/<uuid:tracking_id>/",
        EscrowTransactionViewSet.as_view({"get": "track"}),
    ),
]
# Special URL pattern for sharing transactions by UUID (backend use)

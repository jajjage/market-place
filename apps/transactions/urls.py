from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"transactions", views.TransactionViewSet, basename="transactions")
router.register(r"disputes", views.DisputeViewSet, basename="disputes")
router.register(
    r"transaction-history",
    views.TransactionHistoryViewSet,
    basename="transaction-history",
)

urlpatterns = [
    path("", include(router.urls)),
]
# Special URL pattern for sharing transactions by UUID (backend use)

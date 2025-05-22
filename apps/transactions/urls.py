from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(
    r"transactions", views.EscrowTransactionViewSet, basename="transactions"
)

urlpatterns = [
    path("", include(router.urls)),
]
# Special URL pattern for sharing transactions by UUID (backend use)

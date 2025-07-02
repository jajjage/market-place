from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductWatchlistViewSet


router = DefaultRouter()
router.register(r"watchlists", ProductWatchlistViewSet, basename="watchlist")

urlpatterns = [
    path("", include(router.urls)),
    # Alternative endpoints for specific use cases
]

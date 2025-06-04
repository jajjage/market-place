from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductNegotiationViewSet

router = DefaultRouter()
router.register(r"price-negotiation", ProductNegotiationViewSet, basename="negotiation")

urlpatterns = [
    path("", include(router.urls)),
    # Custom product retrieval endpoints for social sharing
]

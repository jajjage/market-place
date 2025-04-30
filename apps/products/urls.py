# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"products", views.ProductViewSet, basename="products")
router.register(r"category", views.ProductViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
    # Special URL pattern for sharing products by UUID (backend use)
    path(
        "products/uuid/<uuid:uuid>/",
        views.ProductDetailByUUID.as_view(),
        name="product-detail",
    ),
    # Frontend-friendly short URL for sharing on social media
    path(
        "p/<str:short_code>/",
        views.ProductDetailByShortCode.as_view(),
        name="product-short-url",
    ),
]

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from .views import ProductImageViewSet

router = DefaultRouter()
router.register(r"images", ProductImageViewSet, basename="product-image")

urlpatterns = [
    path("api/products/", include(router.urls)),
    # File upload specific endpoints
    path(
        "api/products/<int:product_id>/images/upload/",
        ProductImageViewSet.as_view({"post": "upload_image"}),
    ),
    path(
        "api/products/<int:product_id>/images/bulk-upload/",
        ProductImageViewSet.as_view({"post": "bulk_upload"}),
    ),
    # Other endpoints
    path(
        "api/products/<int:product_id>/images/",
        ProductImageViewSet.as_view({"get": "list"}),
    ),
    path(
        "api/products/<int:product_id>/images/primary/",
        ProductImageViewSet.as_view({"get": "primary"}),
    ),
    path(
        "api/products/<int:product_id>/images/variants/",
        ProductImageViewSet.as_view({"get": "variants"}),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from .views import ProductImageViewSet

router = DefaultRouter()
router.register(r"images", ProductImageViewSet, basename="product-image")

urlpatterns = [
    path("", include(router.urls)),
    # File upload specific endpoints
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.users.views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CookieTokenVerifyView,
    LogoutView,
)
from apps.users.views import CustomUserViewSet

router = DefaultRouter()
router.register("users", CustomUserViewSet)

urlpatterns = [
    # Your other URL patterns
    path("auth/", include(router.urls)),
    path(
        "auth/login/",
        CookieTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("auth/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", CookieTokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
]

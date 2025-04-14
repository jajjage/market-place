from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from apps.users.views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CookieTokenVerifyView,
    CustomSocialProviderView,
    LogoutView,
)
from apps.users.views import CustomUserViewSet

router = DefaultRouter()
router.register("users", CustomUserViewSet, basename="user")

urlpatterns = [
    # Your other URL patterns
    path("auth/", include(router.urls)),
    re_path(
        r"auth/o/(?P<provider>\S+)/$",
        CustomSocialProviderView.as_view(),
        name="provider-auth",
    ),
    path(
        "auth/login/",
        CookieTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("auth/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", CookieTokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
]

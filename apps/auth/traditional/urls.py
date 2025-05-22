from django.urls import path
from .views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CookieTokenVerifyView,
    LogoutView,
)

from rest_framework.routers import DefaultRouter
from djoser.urls.base import router as djoser_base_router


class UserBaseNameRouter(DefaultRouter):
    def get_default_basename(self, viewset):
        """Always return 'user' as basename for user-related viewsets"""
        queryset = getattr(viewset, "queryset", None)
        if queryset is not None:
            model = getattr(queryset, "model", None)
            if model and hasattr(model, "_meta"):
                app_label = model._meta.app_label
                if app_label == "users" or getattr(
                    viewset, "__module__", ""
                ).startswith("djoser."):
                    return "user"
        return super().get_default_basename(viewset)


router = UserBaseNameRouter()

# Re-register Djoser's base endpoints with 'user' basename
for prefix, viewset, basename in djoser_base_router.registry:
    router.register("auth/" + prefix, viewset, basename="user")

urlpatterns = [
    path(
        "auth/login/",
        CookieTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("auth/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", CookieTokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
]

urlpatterns += router.urls

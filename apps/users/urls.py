from django.urls import path, re_path
from apps.users.views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    CookieTokenVerifyView,
    CustomSocialProviderView,
    LogoutView,
    UserRatingViewSet,
    UserStoreViewSet,
    UserAddressViewSet,
    UserProfileViewSet,
)

from rest_framework.routers import DefaultRouter
from djoser.urls.base import router as djoser_base_router


class UserBaseNameRouter(DefaultRouter):
    def get_default_basename(self, viewset):
        # Detect any Djoser viewset whose queryset's model is CustomUser
        queryset = getattr(viewset, "queryset", None)
        model = getattr(queryset, "model", None)
        if model is not None and model.__name__ == "CustomUser":
            return "user"
        return super().get_default_basename(viewset)


router = UserBaseNameRouter()

# Re-register Djoser's base endpoints at root level
for prefix, viewset, basename in djoser_base_router.registry:
    router.register("auth/" + prefix, viewset, basename=basename)

# Register our custom viewsets
router.register(r"users/ratings", UserRatingViewSet, basename="user-rating")
router.register(r"users/store", UserStoreViewSet, basename="user-store")
router.register(r"users/addresses", UserAddressViewSet, basename="user-address")
router.register(r"users/profiles", UserProfileViewSet, basename="user-profile")

urlpatterns = [
    # Your other URL patterns
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

urlpatterns += router.urls

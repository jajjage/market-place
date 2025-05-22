from django.urls import re_path

from .views import CustomSocialProviderView

urlpatterns = [
    # Your other URL patterns
    re_path(
        r"auth/o/(?P<provider>\S+)/$",
        CustomSocialProviderView.as_view(),
        name="provider-auth",
    ),
]

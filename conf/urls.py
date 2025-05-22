from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import environ

# Initialize environment variables
env = environ.Env()

urlpatterns = [
    # TODO⚡ Change the admin url to one of your choice.
    # Please avoid using the default 'admin/' or 'admin-panel/'
    path("admin-panel/", admin.site.urls, name="admin"),
    # TODO ⚡ Disable the auth endpoints you don't need.
    # Enabled: create, profile, login, logout, logoutall
    path("core/", include("apps.core.urls")),
    path("api/v1/", include("apps.auth.google.urls")),
    path("api/v1/", include("apps.auth.traditional.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.products.urls")),
    path(
        "api/v1/", include("apps.transactions.urls")
    ),  # Special URL pattern for sharing transactions by UUID (backend use)
]

if env("DEBUG") == "True":
    import debug_toolbar

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/schema/swagger-ui/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path("__debug__/", include(debug_toolbar.urls)),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

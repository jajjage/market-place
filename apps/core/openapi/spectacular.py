# in /apps/core/openapi.py

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTAuthenticationExtension(OpenApiAuthenticationExtension):
    # This MUST match the path to your custom authentication class
    target_class = "apps.core.authentication.CookieJWTAuthentication"
    name = "cookieAuth"  # The name for the security scheme in OpenAPI

    def get_security_definition(self, auto_schema):
        # Use the cookie name from your Django settings
        cookie_name = getattr(settings, "JWT_AUTH_COOKIE", "access_token")

        return {
            "type": "apiKey",
            "in": "cookie",
            "name": cookie_name,
        }

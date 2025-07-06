from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.CookieJWTAuthentication"
    name = "cookie-jwt"  # how it’ll appear in your OpenAPI “securitySchemes”

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "jwt",  # or whatever cookie name you use
        }

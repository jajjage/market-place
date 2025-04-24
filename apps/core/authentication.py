from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that checks for tokens in cookies.
    Looks for access token in the access cookie, and refresh token in the refresh cookie.
    Falls back to the standard Authorization header if no cookie is present.
    """

    def authenticate(self, request):
        # First try to get the token from the cookie
        access_token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)

        if access_token:
            # If token found in cookie, manually create the header
            validated_token = self.get_validated_token(access_token)
            return self.get_user(validated_token), validated_token

        # Fall back to header authentication if no cookie is present
        return super().authenticate(request)

    # def authenticate_header(self, request):
    #     return "Bearer"

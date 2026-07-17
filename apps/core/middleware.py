import urllib.parse
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom Channels middleware to authenticate users using JWT tokens.
    Checks query parameters (e.g. ?token=...) and HTTP cookies.
    """

    async def __call__(self, scope, receive, send):
        token = None

        # 1. Parse token from query parameters
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = urllib.parse.parse_qs(query_string)
        if "token" in query_params:
            token = query_params["token"][0]

        # 2. Parse token from cookie if not found in query string
        if not token:
            headers = dict(scope.get("headers", []))
            cookie_header = headers.get(b"cookie", b"").decode("utf-8")
            if cookie_header:
                try:
                    cookies = dict(
                        item.split("=", 1)
                        for item in cookie_header.split("; ")
                        if "=" in item
                    )
                    token = cookies.get(settings.JWT_AUTH_COOKIE)
                except Exception:
                    pass

        if token:
            scope["user"] = await self.get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            validated_token = AccessToken(token)
            user_id = validated_token["user_id"]
            return User.objects.get(id=user_id)
        except Exception:
            return AnonymousUser()

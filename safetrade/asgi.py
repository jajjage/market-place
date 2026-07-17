import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.core.middleware import JWTAuthMiddleware
import apps.notifications.routing
import apps.chat.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safetrade.settings.dev")
django_asgi_app = get_asgi_application()
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(
            URLRouter(
                apps.notifications.routing.websocket_urlpatterns
                + apps.chat.routing.websocket_urlpatterns
            )
        ),
    }
)

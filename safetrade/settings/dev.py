import socket
import tempfile
import ast
from .base import *  # noqa
from .base import REST_FRAMEWORK, MIDDLEWARE, INSTALLED_APPS

from .utils.get_env import env


# -----------------------------------------------------------------------------
# Development Settings
# -----------------------------------------------------------------------------
DEBUG = True
ALLOWED_HOSTS = env.get("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1").split(
    ","
)

# -----------------------------------------------------------------------------
# Databases for Development
# -----------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://postgres:postgres@db:5432/postgres",
    ),
}

# -----------------------------------------------------------------------------
# Email Configuration - Development
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env.get("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_USE_TLS = env.get("EMAIL_USE_TLS", default=True, cast_to=bool)
EMAIL_PORT = env.get("EMAIL_PORT", default=587, cast_to=int)
EMAIL_HOST_USER = env.get("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.get("EMAIL_HOST_PASSWORD", default="")

# -----------------------------------------------------------------------------
# CORS Settings - Development
# -----------------------------------------------------------------------------
def parse_cors_origins(value):
    if isinstance(value, (list, tuple)):
        return [str(origin).strip() for origin in value if str(origin).strip()]

    raw_value = str(value).strip()
    if raw_value.startswith("[") and raw_value.endswith("]"):
        try:
            parsed_value = ast.literal_eval(raw_value)
        except (SyntaxError, ValueError):
            parsed_value = None
        if isinstance(parsed_value, (list, tuple)):
            return [
                str(origin).strip().strip("'\"")
                for origin in parsed_value
                if str(origin).strip()
            ]

    return [
        origin.strip().strip("'\"")
        for origin in raw_value.split(",")
        if origin.strip().strip("'\"")
    ]


CORS_ALLOWED_ORIGINS = parse_cors_origins(
    env.get(
        "CORS_ALLOWED_ORIGINS",
        default="http://localhost:3000,http://127.0.0.1:3000",
    )
)

# -----------------------------------------------------------------------------
# Cache - Development
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env.get("REDIS_URL", default="redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.pickle.PickleSerializer",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "safetrade",
        "TIMEOUT": 300,  # 5 minutes default
    },
}
USER_AGENTS_CACHE = "default"

# -----------------------------------------------------------------------------
# Celery - Development
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = env.get("CELERY_BROKER_URL", default="redis://redis:6379")
CELERY_RESULT_BACKEND = env.get("CELERY_RESULT_BACKEND", default="redis://redis:6379")
CELERY_TASK_ALWAYS_EAGER = False  # Keep async for development
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# -----------------------------------------------------------------------------
# REST Framework - Development Settings
# -----------------------------------------------------------------------------
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] += (
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# -----------------------------------------------------------------------------
# Static Files - Development
# -----------------------------------------------------------------------------
STATIC_ROOT = tempfile.mkdtemp()

# -----------------------------------------------------------------------------
# Debug Toolbar
# -----------------------------------------------------------------------------
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INSTALLED_APPS += ["debug_toolbar"]
INTERNAL_IPS = ips + ["127.0.0.1"]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
DEBUG_TOOLBAR_CONFIG = {
    # always show, regardless of cookies or internal‐ips
    "SHOW_TOOLBAR_CALLBACK": lambda request: True,
}

FRONTEND_BASE_URL = (
    "http://localhost:3000"  # or whatever port you use for your frontend
)

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"

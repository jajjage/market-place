from .base import *  # noqa
import sentry_sdk
from .base import env, BASE_DIR

# -----------------------------------------------------------------------------
# Production Settings
# -----------------------------------------------------------------------------
DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# -----------------------------------------------------------------------------
# Databases for Production
# -----------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}

# -----------------------------------------------------------------------------
# Email Configuration - Production
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_PORT = env.int("EMAIL_PORT")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

# -----------------------------------------------------------------------------
# CORS Settings - Production
# -----------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

FRONTEND_DOMAIN = "https://yourescrowapp.com"
# -----------------------------------------------------------------------------
# Cache - Production
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
USER_AGENTS_CACHE = "default"

# -----------------------------------------------------------------------------
# Celery - Production
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")

# -----------------------------------------------------------------------------
# Static Files - Production
# -----------------------------------------------------------------------------
STATIC_ROOT = BASE_DIR / "static_root"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# -----------------------------------------------------------------------------
# Sentry Integration - Production
# -----------------------------------------------------------------------------
sentry_sdk.init(
    dsn=env("SENTRY_DSN"),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

# -----------------------------------------------------------------------------
# Logging - Production
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "%(name)-12s %(levelname)-8s %(message)s"},
        "file": {"format": "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "console"},
        "info_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": f"{BASE_DIR / 'logs'}/info.log",
            "maxBytes": 1000000,
            "backupCount": 10,
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": f"{BASE_DIR / 'logs'}/error.log",
            "maxBytes": 1000000,
            "backupCount": 10,
        },
    },
    "loggers": {
        "": {
            "level": "INFO",
            "handlers": ["console", "info_file", "error_file"],
            "propagate": True,
        },
        "apps.users.views": {
            "level": "INFO",
            "handlers": ["console", "info_file", "error_file"],
            "propagate": False,
        },
    },
}


# -----------------------------------------------------------------------------
# Security Settings - Production
# -----------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
JWT_AUTH_SECURE = True
JWT_AUTH_SAMESITE = "Lax"

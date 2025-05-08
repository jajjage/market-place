from .base import *  # noqa
from .base import REST_FRAMEWORK, MIDDLEWARE, INSTALLED_APPS
import tempfile

import environ
import os
import sys
from pathlib import Path

# Initialize environment variables
env = environ.Env()
root_path = environ.Path(__file__) - 3  # Adjust this based on your folder structure
env.read_env(str(root_path.path(".env")))

# -----------------------------------------------------------------------------
# Development Settings
# -----------------------------------------------------------------------------
DEBUG = True
SECRET_KEY = env(
    "DJANGO_SECRET_KEY", default="django-insecure-development-key-change-me"
)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# -----------------------------------------------------------------------------
# Databases for Development
# -----------------------------------------------------------------------------
DJANGO_DATABASE_URL = env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
DATABASES = {"default": DJANGO_DATABASE_URL}

# -----------------------------------------------------------------------------
# Email Configuration - Development
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# -----------------------------------------------------------------------------
# CORS Settings - Development
# -----------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

# -----------------------------------------------------------------------------
# Cache - Development
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
USER_AGENTS_CACHE = "default"

# -----------------------------------------------------------------------------
# Celery - Development
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="django-db")

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
INSTALLED_APPS += ["debug_toolbar"]
INTERNAL_IPS = ["127.0.0.1"]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

FRONTEND_DOMAIN = "http://localhost:3000"  # or whatever port you use for your frontend


# -----------------------------------------------------------------------------
# Logging - Development
# -----------------------------------------------------------------------------
# helper to build absolute paths off your project root
BASE_DIR = Path(__file__).resolve().parent.parent


def root_path(*parts):
    return str(BASE_DIR.joinpath(*parts))


# create logs directory locally (won’t error if it already exists)
if not os.environ.get("GITHUB_ACTIONS"):
    os.makedirs(root_path("logs"), exist_ok=True)

# base logging config
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "%(name)-12s %(levelname)-8s %(message)s"},
        "file": {"format": "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "stream": sys.stdout,
        },
        # these two get overridden or removed in CI
        "info_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": f"{root_path('logs')}/info.log",
            "maxBytes": 1_000_000,
            "backupCount": 10,
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": f"{root_path('logs')}/error.log",
            "maxBytes": 1_000_000,
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

# If running in GitHub Actions, swap file handlers out for console-only
if os.environ.get("GITHUB_ACTIONS"):
    # drop the file handlers
    LOGGING["handlers"].pop("info_file", None)
    LOGGING["handlers"].pop("error_file", None)

    # adjust root logger to only use console
    LOGGING["loggers"][""]["handlers"] = ["console"]
    LOGGING["loggers"]["apps.users.views"]["handlers"] = ["console"]

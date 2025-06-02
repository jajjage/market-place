from .base import *  # noqa
from .base import REST_FRAMEWORK, MIDDLEWARE, INSTALLED_APPS
import tempfile

from dotenv import load_dotenv
import os
import sys
from pathlib import Path

# Initialize environment variables
# Get the path to the .env file
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

# Load the .env file
load_dotenv(dotenv_path=env_path)
# -----------------------------------------------------------------------------
# Development Settings
# -----------------------------------------------------------------------------
DEBUG = True
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", default="django-insecure-development-key-change-me"
)
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", default=["*"])

# -----------------------------------------------------------------------------
# Databases for Development
# -----------------------------------------------------------------------------
# Database configuration without django-environ
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgres://postgres:postgres@localhost:5432/postgres"
)

if DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "postgres",
            "USER": "postgres",
            "PASSWORD": "postgres",
            "HOST": "localhost",
            "PORT": "5432",
        }
    }
# -----------------------------------------------------------------------------
# Email Configuration - Development
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", default=True)
EMAIL_PORT = os.environ.get("EMAIL_PORT", default=587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", default="")

# -----------------------------------------------------------------------------
# CORS Settings - Development
# -----------------------------------------------------------------------------
# CORS_ALLOWED_ORIGINS = os.environ.get(
#     "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
# ).split(",")
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins.split(",")]
# -----------------------------------------------------------------------------
# Cache - Development
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", default="redis://redis:6379"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
USER_AGENTS_CACHE = "default"

# -----------------------------------------------------------------------------
# Celery - Development
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get(
    "CELERY_BROKER_URL", default="redis://localhost:6379"
)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379"
)

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
        "throttle_file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": "throttling.log",
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
        "utils.rate_limiting": {
            "handlers": ["throttle_file"],
            "level": "DEBUG",
            "propagate": True,
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

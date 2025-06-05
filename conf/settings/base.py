from datetime import timedelta
from pathlib import Path

from corsheaders.defaults import default_headers
import os
from dotenv import load_dotenv

# Initialize environment variables
# Get the path to the .env file
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

# Load the .env file
load_dotenv(dotenv_path=env_path)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# -----------------------------------------------------------------------------
# Basic Config
# -----------------------------------------------------------------------------
ROOT_URLCONF = "conf.urls"
WSGI_APPLICATION = "conf.wsgi.application"
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", default="django-insecure-development-key-change-me"
)
# -----------------------------------------------------------------------------
# Time & Language
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# Security and Users
# -----------------------------------------------------------------------------
AUTH_USER_MODEL = "users.CustomUser"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------
# Applications configuration
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # 3rd party apps
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "django_celery_beat",
    "django_celery_results",
    "drf_spectacular",
    "django_extensions",
    "djoser",
    "social_django",
    # local apps
    "apps.users",
    "apps.core",
    "apps.transactions",
    "apps.notifications",
    "apps.comments",
    "apps.store",
    "apps.disputes",
    "apps.flutterwave",
    "apps.categories",
    "apps.auth.google",
    "apps.auth.traditional",
    "apps.monitoring",
    "apps.products.product_base",
    "apps.products.product_detail",
    "apps.products.product_condition",
    "apps.products.product_brand",
    "apps.products.product_rating",
    "apps.products.product_metadata",
    "apps.products.product_negotiation",
    "apps.products.product_watchlist",
    "apps.products.product_variant",
    "apps.products.product_inventory",
    "apps.products.product_image",
    "apps.products.product_breadcrumb",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "apps.monitoring.middleware.PerformanceMonitoringMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# -----------------------------------------------------------------------------
# Auth Backends
# -----------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "social_core.backends.google.GoogleOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]


# -----------------------------------------------------------------------------
# Rest Framework
# -----------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.core.authentication.CookieJWTAuthentication",
    ),
    # "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user_login": "5/minute",
        "watchlist": "500/hour",
        "watchlist_toggle": "100/hour",
        "watchlist_bulk": "20/hour",
        "watchlist_admin": "1000/hour",
        "ratings_create": "100/hour",
        "vote_helpful": "100/hour",
        "category": "1000/hour",
        "product_condition": "2000/hour",
        "product_list": "1000/min",
        "product_detail": "1000/min",
        "product_create": "100/min",
        "brand_search": "30/min",
        "brand_create": "100/min",
        "breadcrumb": "200/min",
    },
}

# -----------------------------------------------------------------------------
# Djoser
# -----------------------------------------------------------------------------

DJOSER = {
    "PASSWORD_RESET_CONFIRM_URL": "auth/password-reset-confirm/{uid}/{token}",
    "SET_PASSWORD_RETYPE": True,
    "PASSWORD_RESET_CONFIRM_RETYPE": True,
    "TOKEN_MODEL": None,
    "SOCIAL_AUTH_ALLOWED_REDIRECT_URIS": [
        "http://localhost:3000/auth/google/",
        "http://127.0.0.1:3000/auth/google/",
    ],
    "SERIALIZERS": {
        "user": "apps.users.serializers.UserSerializer",
        "current_user": "apps.users.serializers.UserSerializer",
    },
    "PERMISSIONS": {
        "user": ["rest_framework.permissions.IsAuthenticated"],
        "user_list": ["rest_framework.permissions.IsAuthenticated"],
    },
}

# -----------------------------------------------------------------------------
# Simple JWT
# -----------------------------------------------------------------------------


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived access tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),  # Longer-lived refresh tokens
    "ROTATE_REFRESH_TOKENS": True,  # Generate new refresh token when refreshing
    "BLACKLIST_AFTER_ROTATION": True,  # Blacklist old refresh tokens
    "TOKEN_OBTAIN_SERIALIZER": "apps.auth.traditional.serializers.CustomTokenObtainSerializer",
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.environ.get("DJANGO_SECRET_KEY", default="django-insecure$@"),
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",  # Using UUID field from your User model
    "USER_ID_CLAIM": "user_id",
    # Custom claims to include user type and verification status
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    # Add token to blacklist when user logs out
    "BLACKLIST_ENABLED": True,
}

# Configure token blacklist to use Redis
SIMPLE_JWT_BLACKLIST_CACHE = "default"

# - -----------------------------------------------------------------------------
# JWT Authentication
# ------------------------------------------------------------------------------
JWT_AUTH_COOKIE = "access_token"
JWT_AUTH_REFRESH_COOKIE = "refresh_token"
JWT_REFRESH_THRESHOLD = 300  # 5 minutes in seconds
JWT_ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
JWT_REFRESH_TOKEN_LIFETIME = timedelta(days=1)
JWT_AUTH_SECURE = False
JWT_AUTH_SAMESITE = (
    "Lax"  # if os.environ.get("JWT_AUTH_SECURE", default="False") == "True" else "None"
)
JWT_AUTH_HTTPONLY = True
JWT_AUTH_PATH = "/"

# -----------------------------------------------------------------------------
# Google OAuth
# -----------------------------------------------------------------------------
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", default=""
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET", default=""
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]
SOCIAL_AUTH_GOOGLE_OAUTH2_EXTRA_DATA = ["first_name", "last_name"]
SOCIAL_AUTH_GOOGLE_OAUTH2_AUTH_EXTRA_ARGUMENTS = {
    "redirect_uri": "http://localhost:3000/auth/google/",
}


# -----------------------------------------------------------------------------
# CORS Settings
# -----------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = list(default_headers) + [
    "cache-control",
]


# -----------------------------------------------------------------------------
# Email Template
# -----------------------------------------------------------------------------

DOMAIN = os.environ.get("DOMAIN", default="localhost:3000")
SITE_NAME = "Safe Trade MarketPlace"

# -----------------------------------------------------------------------------
# Social Auth Pipeline
# -----------------------------------------------------------------------------
SOCIAL_AUTH_PIPELINE = (
    # Get user information from social provider
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    # Get or create the user account
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    # Store OAuth data first
    "apps.auth.google.social_auth_pipeline.store_oauth_data",
    "apps.auth.google.social_auth_pipeline.store_user_details",
    # Create profile last, after user_type is set
    "apps.auth.google.social_auth_pipeline.create_user_profile",
)

# -----------------------------------------------------------------------------
# DRF Spectacular Settings
# -----------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Safe Trade MarketPlace API",
    "DESCRIPTION": "A comprehensive starting point for your new API with Django and DRF",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# -----------------------------------------------------------------------------
# Static & Media Base Configuration
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(BASE_DIR / "static")]
MEDIA_URL = "/media/"
MEDIA_ROOT = str(BASE_DIR / "media_root")
ADMIN_MEDIA_PREFIX = STATIC_URL + "admin/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Optional: Custom media base URL for production
# MEDIA_BASE_URL = 'https://your-cdn-domain.com/media/'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Make sure media directory exists
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(os.path.join(MEDIA_ROOT, "products", "images"), exist_ok=True)

# -----------------------------------------------------------------------------
# Celery
# -----------------------------------------------------------------------------
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/Santiago"
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"

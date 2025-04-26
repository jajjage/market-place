from datetime import timedelta
from pathlib import Path

from corsheaders.defaults import default_headers

import environ

# Initialize environment variables
env = environ.Env()
root_path = environ.Path(__file__) - 3  # Adjust this based on your folder structure
env.read_env(str(root_path.path(".env")))
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# -----------------------------------------------------------------------------
# Basic Config
# -----------------------------------------------------------------------------
ROOT_URLCONF = "conf.urls"
WSGI_APPLICATION = "conf.wsgi.application"
SECRET_KEY = env(
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
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [root_path("templates")],
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

DJANGO_DATABASE_URL = env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
DATABASES = {"default": DJANGO_DATABASE_URL}


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
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "user": "1000/day",
        "anon": "100/day",
        "user_login": "5/minute",
    },
}

# -----------------------------------------------------------------------------
# Djoser
# -----------------------------------------------------------------------------

DJOSER = {
    "PASSWORD_RESET_CONFIRM_URL": "auth/password-reset-confirm/{uid}/{token}",
    "USER_CREATE_PASSWORD_RETYPE": True,
    "SET_PASSWORD_RETYPE": True,
    "PASSWORD_RESET_CONFIRM_RETYPE": True,
    "TOKEN_MODEL": None,
    "SOCIAL_AUTH_ALLOWED_REDIRECT_URIS": env.list(
        "SOCIAL_AUTH_ALLOWED_REDIRECT_URIS", default=""
    ),
    "SERIALIZERS": {
        "current_user": "apps.users.serializers.UserSerializer",
    },
    # "VIEWS": {
    #     "users": "apps.users.views.CustomUserViewSet",
    #     "user_list": "apps.users.views.CustomUserViewSet",
    #     "activation": "apps.users.views.CustomUserViewSet",
    #     "set_password": "apps.users.views.CustomUserViewSet",
    #     "reset_password": "apps.users.views.CustomUserViewSet",
    #     "reset_password_confirm": "apps.users.views.CustomUserViewSet",
    #     "me": "apps.users.views.CustomUserViewSet",
    # },
}

# -----------------------------------------------------------------------------
# Simple JWT
# -----------------------------------------------------------------------------


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # Short-lived access tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),  # Longer-lived refresh tokens
    "ROTATE_REFRESH_TOKENS": True,  # Generate new refresh token when refreshing
    "BLACKLIST_AFTER_ROTATION": True,  # Blacklist old refresh tokens
    "TOKEN_OBTAIN_SERIALIZER": "apps.users.serializers.CustomTokenObtainSerializer",
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("DJANGO_SECRET_KEY", default="django-insecure$@"),
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
JWT_AUTH_SAMESITE = "Lax"
JWT_AUTH_HTTPONLY = True
JWT_AUTH_PATH = "/"

# -----------------------------------------------------------------------------
# Google OAuth
# -----------------------------------------------------------------------------
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", default="")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env("SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET", default="")
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]
SOCIAL_AUTH_GOOGLE_OAUTH2_EXTRA_DATA = ["first_name", "last_name"]

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

DOMAIN = env("DOMAIN", default="localhost:3000")
SITE_NAME = "Safe Trade MarketPlace"

# -----------------------------------------------------------------------------
# Social Auth Pipeline
# -----------------------------------------------------------------------------
SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "apps.users.social_auth_pipeline.set_user_type",  # Your custom function
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
    "apps.users.social_auth_pipeline.activate_social_user",  # Your activation function
    "apps.users.social_auth_pipeline.create_user_profile",  # Add this after user creation
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
STATICFILES_DIRS = [root_path("static")]
MEDIA_URL = "/media/"
MEDIA_ROOT = root_path("media_root")
ADMIN_MEDIA_PREFIX = STATIC_URL + "admin/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------------------------------------------------------
# Celery
# -----------------------------------------------------------------------------
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/Santiago"
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"

import environ
from datetime import timedelta
from pathlib import Path

from corsheaders.defaults import default_headers
import os

from .utils.get_env import env

# # Initialize environment variables with django-environ
BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


# -----------------------------------------------------------------------------
# Basic Config
# -----------------------------------------------------------------------------
ROOT_URLCONF = "safetrade.urls"
ASGI_APPLICATION = "safetrade.asgi.application"
WSGI_APPLICATION = "safetrade.wsgi.application"
SECRET_KEY = env.get("DJANGO_SECRET_KEY", default="django-insecure$@")
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
    "daphne",
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
    "django_elasticsearch_dsl",
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
    "apps.users.apps.UsersConfig",
    "apps.core.apps.CoreConfig",
    "apps.transactions.apps.TransactionsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.comments.apps.CommentsConfig",
    "apps.store.apps.StoreConfig",
    "apps.disputes.apps.DisputesConfig",
    "apps.flutterwave.apps.FlutterwaveConfig",
    "apps.categories.apps.CategoriesConfig",
    "apps.auth.google.apps.GoogleAuthConfig",
    "apps.auth.traditional.apps.TraditionalAuthConfig",
    "apps.monitoring.apps.MonitoringConfig",
    "apps.search.apps.SearchConfig",
    "apps.chat.apps.ChatConfig",
    "apps.products.product_base.apps.ProductBaseConfig",
    "apps.products.product_brand.apps.ProductBrandConfig",
    "apps.products.product_common.apps.ProductCommonConfig",
    "apps.products.product_condition.apps.ProductConditionConfig",
    "apps.products.product_detail.apps.ProductDetailConfig",
    "apps.products.product_image.apps.ProductImageConfig",
    "apps.products.product_inventory.apps.ProductInventoryConfig",
    "apps.products.product_metadata.apps.ProductMetadataConfig",
    "apps.products.product_negotiation.apps.ProductPriceNegotiationConfig",
    "apps.products.product_rating.apps.ProductRatingConfig",
    "apps.products.product_variant.apps.ProductVariantConfig",
    "apps.products.product_watchlist.apps.ProductWatchlistConfig",
    "apps.products.product_search.apps.ProductSearchConfig",
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
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
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
        "category": "1000/min",
        "product_condition": "2000/min",
        "product_list": "1000/min",
        "product_detail": "1000/min",
        "product_create": "100/min",
        "product_update": "100/min",
        "product_delete": "100/min",
        "product_stats": "100/min",
        "product_featured": "100/min",
        "product_search": "100/min",
        "brand_search": "30/min",
        "brand_create": "100/min",
        "escrow_transaction_list": "100/min",
        "escrow_transaction_create": "10/min",
        "escrow_transaction_update": "50/min",
        "escrow_transaction_track": "200/min",
        "my_purchases": "100/min",
        "my_sales": "100/min",
        "negotiation": "20/min",  # 20 negotiation actions per min
        "negotiation_initiate": "5/min",  # 5 new negotiations per min
        "negotiation_respond": "30/min",
        "rating_create": "10/hour",
        "rating_view": "100/hour",
        "dispute_create": "100/min",
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
    "SOCIAL_AUTH_ALLOWED_REDIRECT_URIS": env.get(
        "SOCIAL_AUTH_ALLOWED_REDIRECT_URIS",
        default=[
            "http://localhost:3000/auth/google/",
            "http://127.0.0.1:3000/auth/google/",
        ],
    ).split(","),
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
    "SIGNING_KEY": env.get("DJANGO_SECRET_KEY", default="django-insecure$@"),
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
JWT_AUTH_SECURE = env.get("JWT_AUTH_SECURE", default=False, cast_to=bool)
JWT_AUTH_SAMESITE = env.get("JWT_AUTH_SAMESITE", default="Lax")
JWT_AUTH_HTTPONLY = True
JWT_AUTH_PATH = "/"

# -----------------------------------------------------------------------------
# Google OAuth
# -----------------------------------------------------------------------------
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env.get("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", default="")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env.get(
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

DOMAIN = env.get("DOMAIN", default="localhost:3000")
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
    "TITLE": "Safe Trade Marketplace API",
    "DESCRIPTION": "API for the Safe Trade Marketplace",
    "VERSION": "1.0.0",
    "EXTENSIONS": [
        "apps.core.openapi.spectacular.CookieJWTAuthenticationExtension",
    ],
    "ENUM_NAME_OVERRIDES": {
        # "TaskResultStatusEnum": "django_celery_results.models.TaskResult.STATUS_CHOICES",
        "EscrowTransactionStatusEnum": "apps.transactions.models.transaction.EscrowTransaction.STATUS_CHOICES",
        "DisputeStatusEnum": "apps.disputes.models.DisputeStatus",
        "DisputeReasonEnum": "apps.disputes.models.DisputeReason",
        "ProductStatusEnum": "apps.products.product_base.models.Product.ProductsStatus",
        "BrandRequestStatusEnum": "apps.products.product_brand.models.BrandRequest.Status",
        "ProductDetailStatusEnum": "apps.products.product_detail.models.ProductDetail.DetailType",
        "ProductDetailTemplateStatusEnum": "apps.products.product_detail.models.ProductDetailTemplate.DetailType",
        "PriceNegotiationStatusEnum": "apps.products.product_negotiation.models.PriceNegotiation.STATUS_CHOICES",
    },
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

# Timezone configuration
CELERY_TIMEZONE = TIME_ZONE  # Use your Django timezone
CELERY_ENABLE_UTC = True
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"

from .celery.celery_beat_schedule import get_celery_beat_schedule

CELERY_BEAT_SCHEDULE = get_celery_beat_schedule()

# Task execution configuration
CELERY_TASK_ALWAYS_EAGER = False  # Set to True for synchronous execution in tests
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = False

# Logging configuration for Celery
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
CELERY_WORKER_TASK_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

from .celery.celery_workers import get_worker_config

# Get worker configuration
WORKER_CONFIG = get_worker_config()

# Celery worker settings
CELERY_WORKER_PREFETCH_MULTIPLIER = WORKER_CONFIG["prefetch_multiplier"]
CELERY_WORKER_MAX_TASKS_PER_CHILD = WORKER_CONFIG["max_tasks_per_child"]
CELERY_WORKER_MAX_MEMORY_PER_CHILD = WORKER_CONFIG["max_memory_per_child"]
CELERY_WORKER_CONCURRENCY = WORKER_CONFIG["concurrency"]
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Task routing for different queues
CELERY_TASK_ROUTES = {
    # High priority tasks
    "apps.transactions.tasks.transitions_tasks.check_expired_transactions": {
        "queue": "high_priority",
        "routing_key": "high_priority",
    },
    "apps.transactions.tasks.periodic_migration.ensure_timeout_scheduling": {
        "queue": "high_priority",
        "routing_key": "high_priority",
    },
    "apps.products.product_search.tasks.bulk_update_seo_keywords": {
        "queue": "high_priority",
        "routing_key": "high_priority",
    },
    "apps.products.product_search.tasks.update_popularity_scores": {
        "queue": "high_priority",
        "routing_key": "high_priority",
    },
    # Medium priority tasks
    "apps.transactions.tasks.periodic_migration.validate_timeout_consistency": {
        "queue": "medium_priority",
        "routing_key": "medium_priority",
    },
    "apps.transactions.tasks.periodic_migration.auto_fix_timeout_issues": {
        "queue": "medium_priority",
        "routing_key": "medium_priority",
    },
    # Low priority tasks
    "apps.transactions.tasks.periodic_migration.generate_timeout_health_report": {
        "queue": "low_priority",
        "routing_key": "low_priority",
    },
    "apps.transactions.tasks.transitions_tasks.cleanup_completed_timeouts": {
        "queue": "low_priority",
        "routing_key": "low_priority",
    },
    # Default queue for other tasks
    "apps.transactions.tasks.*": {
        "queue": "default",
        "routing_key": "default",
    },
    "apps.products.product_negotiation.tasks.*": {
        "queue": "default",
        "routing_key": "default",
    },
}

# Queue configuration
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES = {
    "high_priority": {
        "exchange": "high_priority",
        "exchange_type": "direct",
        "routing_key": "high_priority",
    },
    "medium_priority": {
        "exchange": "medium_priority",
        "exchange_type": "direct",
        "routing_key": "medium_priority",
    },
    "low_priority": {
        "exchange": "low_priority",
        "exchange_type": "direct",
        "routing_key": "low_priority",
    },
    "default": {
        "exchange": "default",
        "exchange_type": "direct",
        "routing_key": "default",
    },
}

# -----------------------------------------------------------------------------
# Import modular settings
# -----------------------------------------------------------------------------
from .utils.performance import *  # noqa: F403 F401
from .utils.logging import *  # noqa: F403 F401
from .utils.cache_keys import *  # noqa: F403 F401
from .utils.negotiation import *  # noqa: F403 F401
from .utils.search_settings import *  # noqa: F403 F401

# -----------------------------------------------------------------------------
# Channels Configuration
# -----------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("redis", 6379)],
        },
    },
}

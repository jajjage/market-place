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
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
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
        "LOCATION": os.environ.get("REDIS_URL", default="redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.pickle.PickleSerializer",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "safetrade",
        "TIMEOUT": 300,  # 5 minutes default
    },
    # "long_term": {
    #     "BACKEND": "django_redis.cache.RedisCache",
    #     "LOCATION": os.environ.get("REDIS_URL", default="redis://redis:6379/2"),
    #     "OPTIONS": {
    #         "CLIENT_CLASS": "django_redis.client.DefaultClient",
    #     },
    #     "KEY_PREFIX": "safetrade_long",
    #     "TIMEOUT": 3600,  # 1 hour default
    # },
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
INSTALLED_APPS += ["debug_toolbar"]
INTERNAL_IPS = ["127.0.0.1"]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

FRONTEND_DOMAIN = "http://localhost:3000"  # or whatever port you use for your frontend


# -----------------------------------------------------------------------------
# Logging - Development
# -----------------------------------------------------------------------------
# helper to build absolute paths off your project root
BASE_DIR = Path(__file__).resolve().parent.parent

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"


# ----------------------------------------------------------------------------------
# Performance API prefixes for logging
# -----------------------------------------------------------------------------------
PERFORMANCE_API_PREFIXES = {
    # key = prefix to match in request.path
    # value = “short name” used to build logger name as "{short_name}_performance"
    "/api/v1/brands": "brands",
    "/api/v1/inventory": "inventory",
    "/api/v1/detail": "detail",
    "/api/v1/watchlist": "watchlist",
    "/api/v1/images": "images",
    "/api/v1/escrow": "escrow",
    "/api/v1/negotiation": "negotiation",
    "/api/v1/ratings": "ratings",
    "/api/v1/conditions": "conditions",
    "/api/v1/categories": "categories",
    "/api/v1/products": "products",
    "/api/v1/variants": "variant",
    # …add more as needed…
}

# 2) DB‐related thresholds:
SLOW_QUERY_MS_THRESHOLD = 1000  # log any query whose mean_time > 1000ms
# Which “table patterns” (regex) to check in pg_stat_statements:
PG_TABLE_PATTERNS = [
    r"^product_.*",  # e.g., product_images, product_variants, etc.
    r"^transaction_.*",  # Example for another pattern
    r"^customer_.*",
]

# 3) Cache‐hit ratio threshold:
CACHE_HIT_RATIO_THRESHOLD = 80  # in percent

# 4) Celery‐beat interval (in seconds) for the periodic performance check:
PERFORMANCE_CHECK_INTERVAL_SECONDS = 300  # run every 5 minutes

SLOW_REQUEST_THRESHOLD_SEC = 2  # log any request taking longer than 2 seconds
# ─────────────────────────────────────────────────────
# Create a “logs” directory next to this settings file:
# ─────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create one log path per performance prefix
PERFORMANCE_LOG_PATHS = {
    short_name: LOG_DIR / f"{short_name}_performance.log"
    for short_name in PERFORMANCE_API_PREFIXES.values()
}
MONITORING_LOG_PATH = LOG_DIR / "monitoring.log"
ERROR_LOG_PATH = LOG_DIR / "error.log"
INFO_LOG_PATH = LOG_DIR / "info.log"
THROTTLE_LOG_PATH = LOG_DIR / "throttling.log"
print(MONITORING_LOG_PATH)
# If running locally (not in GitHub Actions), ensure folder exists as well:
if not os.environ.get("GITHUB_ACTIONS"):
    os.makedirs(LOG_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────
# base logging config
# ─────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": "%(name)-12s %(levelname)-8s %(message)s"},
        "file": {"format": "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"},
        # ← Add “verbose” here:
        "verbose": {
            "format": "%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "stream": sys.stdout,
        },
        "throttle_file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": str(THROTTLE_LOG_PATH),
            "maxBytes": 1_000_000,
            "backupCount": 10,
        },
        # these two get overridden or removed in CI
        "info_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": str(INFO_LOG_PATH),
            "maxBytes": 1_000_000,
            "backupCount": 10,
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": str(ERROR_LOG_PATH),
            "maxBytes": 1_000_000,
            "backupCount": 10,
        },
        **{
            f"{short_name}_performance_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(path),
                "formatter": "file",
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "level": "INFO",
            }
            for short_name, path in PERFORMANCE_LOG_PATHS.items()
        },
        "monitoring_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(MONITORING_LOG_PATH),
            "formatter": "file",
            "maxBytes": 5 * 1024 * 1024,  # e.g. 5 MB
            "backupCount": 3,
            "level": "INFO",
        },
    },
    "loggers": {
        # root logger
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
            "level": "INFO",
            "propagate": True,
        },
        **{
            f"{short_name}_performance": {
                "handlers": [f"{short_name}_performance_file"],
                "level": "INFO",
                "propagate": False,
            }
            for short_name in PERFORMANCE_API_PREFIXES.values()
        },
        # ───────────────────────────────────────────
        # 3. Fallback “monitoring” logger:
        # ───────────────────────────────────────────
        "monitoring": {
            "handlers": ["monitoring_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# If running under CI (e.g. GitHub Actions), drop all file handlers:
if os.environ.get("GITHUB_ACTIONS"):
    # pop any file‐based handlers:
    for h in list(LOGGING["handlers"].keys()):
        if h.endswith("_file"):
            LOGGING["handlers"].pop(h, None)

    # set all loggers to use only console handler:
    LOGGING["loggers"][""]["handlers"] = ["console"]
    if "monitoring" in LOGGING["loggers"]:
        LOGGING["loggers"]["monitoring"]["handlers"] = ["console"]
    for short_name in PERFORMANCE_API_PREFIXES.values():
        logger_name = f"{short_name}_performance"
        if logger_name in LOGGING["loggers"]:
            LOGGING["loggers"][logger_name]["handlers"] = ["console"]
    LOGGING["loggers"]["apps.users.views"]["handlers"] = ["console"]
    LOGGING["loggers"]["utils.rate_limiting"]["handlers"] = ["console"]

# -----------------------------------------------------------------------------
# CENTRALIZED CACHE-KEY TEMPLATES
#
# For each “resource” you want to cache, list every “key name” you might use.
# Use Python‐format placeholders for variable parts.
#
# Usage:
#    CacheKeyManager.make_key("brand", "detail", id=42)
#    → "brand:detail:42"
#
#    CacheKeyManager.make_key("inventory", "stock", id=10, variant=3)
#    → "inventory:stock:10:3"
#
#    CacheKeyManager.make_pattern("brand", "variants", id=42)
#    → "brand:variants:42:*"
#
# The code will always prepend Django’s KEY_PREFIX automatically.
# -----------------------------------------------------------------------------
CACHE_KEY_TEMPLATES = {
    "product_catalog": {
        # Your requested key pattern: product_catalog:all:page:{n}:sort:{criteria}:v{version}
        "all_paginated": "product_catalog:all:page:{page}:sort:{sort_criteria}:v{version}",
        "all_pattern": "product_catalog:all:*",  # For bulk deletion - NO PLACEHOLDERS
        # Other catalog keys
        "category_list": "product_catalog:category:{category_id}:page:{page}:sort:{sort_criteria}:v{version}",
        "brand_list": "product_catalog:brand:{brand_id}:page:{page}:sort:{sort_criteria}:v{version}",
        "search_results": "product_catalog:search:{search_hash}:page:{page}:sort:{sort_criteria}:v{version}",
        # Wildcard patterns for bulk deletion - SOME REQUIRE PARAMS
        "category_pattern": "product_catalog:category:{category_id}:*",  # Requires category_id
        "brand_pattern": "product_catalog:brand:{brand_id}:*",  # Requires brand_id
        "search_pattern": "product_catalog:search:*",  # No params needed
    },
    "product_base": {
        "detail": "product_base:detail:{id}",
        "detail_by_shortcode": "product_base:detail_by_shortcode:{short_code}",
        # FIXED: Separate exact keys from patterns
        "list": "product_base:list:{params}",  # For exact keys
        "list_all_pattern": "product_base:list:*",  # For ALL list deletion - NO PARAMS NEEDED
        "my_products": "product_base:my_products:{user_id}",
        "my_products_pattern": "product_base:my_products:*",  # For ALL user products - NO PARAMS
        "featured": "product_base:featured",
        "stats": "product_base:stats:{user_id}",
        "stats_pattern": "product_base:stats:*",  # For ALL user stats - NO PARAMS
        "watchers": "product_base:watchers:{id}",
        "watchers_pattern": "product_base:watchers:*",  # For ALL watchers - NO PARAMS
        "share_links": "product_base:share_links:{short_code}",
        "share_links_pattern": "product_base:share_links:*",  # For ALL share links - NO PARAMS
        "by_condition": "product_base:by_condition:{condition_id}",
        "by_condition_pattern": "product_base:by_condition:*",  # For ALL conditions - NO PARAMS
        "toggle_active": "product_base:toggle_active:{id}",
        "toggle_featured": "product_base:toggle_featured:{id}",
        # Specific user patterns - REQUIRE user_id parameter
        "user_specific_pattern": "product_base:my_products:{user_id}",  # Specific user only
        "user_stats_pattern": "product_base:stats:{user_id}",  # Specific user stats
    },
    "brand": {
        # Exact keys (no wildcard) → use make_key("brand", key_name, **kwargs)
        "detail": "brand:detail:{id}",
        "stats": "brand:stats:{id}",
        "analytics": "brand:analytics:{brand_id}:{days}",  # Added missing analytics key
        # Wildcard patterns → use make_pattern("brand", key_name, **kwargs)
        "variants": "brand:variants:{id}:{variant_id}",  # for a single variant
        "variants_all": "brand:variants:{id}:*",  # wildcard to delete all variants
        "featured": "brand:featured:*",  # Fixed: changed from "brands:" to "brand:"
        "list": "brand:list:*",  # wildcard for all paginated lists
        # Additional patterns for comprehensive invalidation
        "all_analytics": "brand:analytics:*",  # wildcard for all analytics
        "all_stats": "brand:stats:*",  # wildcard for all stats
        "all_details": "brand:detail:*",  # wildcard for all details
    },
    "brand_variant": {
        "all": "brand:variants:{brand_id}:*",
        "types": "brand",
        # for invalidating all variants of a brand
    },
    "product_condition": {
        "detail": "condition:detail:{id}",
        "list": "condition:list:*",
        "active_conditions": "condition:active_conditions:{include_stats}",
        "popular_conditions": "condition:popular_conditions:{limit}",
        "analytics": "condition:analytics:{condition_id}",
    },
    "product_variant": {
        "types": "variant:types:active_only:{active_only}:with_options:{with_options}",
        "detail": "variant:detail:{params}",
        "options": "variant:options:product_id:{product_id}:option_ids:{option_ids}",
        "popular_conditions": "variant:popular_conditions:{limit}",
        "analytics": "variant:analytics:{variant_id}",
    },
    "product_inventory": {
        "detail": "inventory:detail:{id}",
        "price_stats": "inventory:price_stats:{id}",
        "stock": "inventory:stock:{id}:{variant_id}",
        "stock_all": "inventory:stock:{id}:*",  # wildcard for all stock keys of an item
        "list": "inventory:list:*",
    },
    "product_watchlist": {
        "user_list": "watchlist:user:{id}:items",  # for a single user’s watchlist
        "items_all": "watchlist:items:{id}:*",  # wildcard to delete all items of a user
    },
    # Cache configuration in settings
    "product_image": {
        "list": "image:list:{product_id}",
        "primary": "image:primary:{product_id}",
        "variants": "image:variants:{product_id}",
        "variants_all": "image:variants:{product_id}:*",  # For invalidation
    },
    "product_detail": {
        "list": "detail:list:{product_id}",
        "grouped": "detail:grouped:{product_id}",
        "highlighted": "detail:highlighted:{product_id}",
        "template": "detail:template:{template_id}",
        "category": "detail:category:{category_id}",
        "detail_type": "detail:type:{detail_type}",
    },
    "product_meta": {
        "detail": "meta:detail:{id}",
        "list": "meta:list",
        "featured": "meta:featured",
        "views_buffer": "meta:views_buffer:{id}",
    },
    "category": {
        "detail": "category:detail:{id}",
        "list": "category:list",
        "tree": "category:tree:{max_depth}:{include_inactive}",
        "subcategory_ids": "category:subcategory_ids:{category_id}",
        "popular_categories": "category:popular_categories:{limit}",
        "breadcrumb_path": "category:breadcrumb_path:{category_id}",
    },
    "escrow_transaction": {
        "detail": "escrow:transaction:detail:{id}",
        "list_user": "escrow:transaction:list:{user_id}:{params}",
        "my_purchases": "escrow:transaction:purchases:user:{user_id}",
        "my_sales": "escrow:transaction:sales:{user_id}",
        "tracking": "escrow:transaction:{user_id}:{tracking_id}",
        "status_counts": "escrow:transaction:counts:{user_id}",
    },
    "negotiation": {
        "detail": "negotiation:detail:{id}",
        "user_list": "negotiation:user:{user_id}:status:{status}:role:{role}:product:{product}",
        "stats": "negotiation:stats:product:{product_id}",
        "user_history": "negotiation:history:user:{user_id}:limit:{limit}",
        "active_count": "negotiation:active:user:{user_id}",
        # Wildcard patterns for invalidation
        "user_all": "negotiation:user:{user_id}:*",
        "product_all": "negotiation:*:product:{product_id}:*",
    },
    "product_rating": {
        "detail": "ratings:detail:{id}",
        "list": "ratings:list:{product_id}:params:{params}",
        "user_list": "ratings:user:{user_id}:params:{params}",
        "user_stats": "ratings:user_stats:{user_id}",
        "aggregate": "ratings:aggregate:{product_id}",
        "can_rate": "ratings:can_rate:{product_id}",
        "recent": "ratings:recent:limit:{limit}",
        "flagged": "ratings:flagged",
        # Wildcard patterns for bulk deletion
        "all_ratings": "ratings:*",  # For all ratings
    },
    # …add new resources here as needed…
}

# Negotiation Feature Settings
NEGOTIATION_SETTINGS = {
    # Business Rules
    "MAX_CONCURRENT_NEGOTIATIONS": 5,  # Max active negotiations per user
    "MAX_NEGOTIATION_ROUNDS": 5,  # Max back-and-forth rounds
    "DEFAULT_NEGOTIATION_DEADLINE_HOURS": 72,  # Default 3 days
    "MIN_OFFER_PERCENTAGE": 30,  # Minimum 30% of original price
    "AUTO_EXPIRE_HOURS": 168,  # Auto-expire after 7 days
    # Rate Limiting
    "HOURLY_NEGOTIATION_LIMIT": 20,
    "DAILY_NEGOTIATION_LIMIT": 50,
    "SPAM_DETECTION_THRESHOLD": 10,  # Same user, same product
    # Caching
    "CACHE_TIMEOUT_SHORT": 300,  # 5 minutes
    "CACHE_TIMEOUT_MEDIUM": 1800,  # 30 minutes
    "CACHE_TIMEOUT_LONG": 3600,  # 1 hour
    # Notifications
    "NOTIFY_SELLER_NEW_OFFER": True,
    "NOTIFY_BUYER_RESPONSE": True,
    "NOTIFY_EXPIRATION_WARNING": True,
    "EXPIRATION_WARNING_HOURS": 24,  # Warn 24 hours before expiry
    # Analytics
    "TRACK_NEGOTIATION_METRICS": True,
    "METRICS_RETENTION_DAYS": 365,
}

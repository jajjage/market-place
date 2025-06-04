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
        "LOCATION": os.environ.get("REDIS_URL", default="redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "brand_api",
        "TIMEOUT": 300,  # 5 minutes default
    },
    "long_term": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", default="redis://redis:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "product_long",
        "TIMEOUT": 3600,  # 1 hour default
    },
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
    # …add more as needed…
}

# 2) DB‐related thresholds:
SLOW_QUERY_MS_THRESHOLD = 1000  # log any query whose mean_time > 1000ms
# Which “table patterns” (regex) to check in pg_stat_statements:
PG_TABLE_PATTERNS = [
    r"^product_.*",  # e.g. product_images, product_variants, etc.
    # add whatever patterns you care about
]

# 3) Cache‐hit ratio threshold:
CACHE_HIT_RATIO_THRESHOLD = 80  # in percent

# 4) Celery‐beat interval (in seconds) for the periodic performance check:
PERFORMANCE_CHECK_INTERVAL_SECONDS = 300  # run every 5 minutes


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
# Cache Invalidation Patterns
# -----------------------------------------------------------------------------

CACHE_INVALIDATION_PATTERNS = {
    "brand": [
        ("BRAND_DETAIL", {"id": "{id}"}),
        ("BRAND_STATS", {"id": "{id}"}),
        "brand:variants:{id}:*",
        "brands:featured:*",
        "brand:list:*",
    ],
    "inventory": [
        ("INVENTORY_DETAIL", {"id": "{id}"}),
        ("INVENTORY_PRICE", {"id": "{id}"}),
        "inventory:stock:{id}:*",
        "inventory:list:*",
    ],
    "detail": [
        ("DETAIL_PAGE", {"id": "{id}"}),
        "detail:related:{id}:*",
    ],
    "watchlist": [
        ("WATCHLIST_USER", {"id": "{id}"}),
        "watchlist:items:{id}:*",
    ],
    # …etc…
}


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
    "product_base": {
        "detail": "product_base:detail:{id}",
        "detail_by_shortcode": "product_base:detail_by_shortcode:{short_code}",
        "list": "product_base:list:{page}:{filters}",
        "my_products": "product_base:my_products:{user_id}:{page}:{filters}",
        "featured": "product_base:featured",
        "stats": "product_base:stats:{user_id}",
        "watchers": "product_base:watchers:{id}",
        "share_links": "product_base:share_links:{short_code}",
        "by_condition": "product_base:by_condition:{condition_id}:{filters}",
        "toggle_active": "product_base:toggle_active:{id}",
        "toggle_featured": "product_base:toggle_featured:{id}",
        # Add more as needed for other endpoints
    },
    "product_breadcrumb": {
        "product": "product_breadcrumb:product:{product_id}",
        "all": "product_breadcrumb:all:*",
    },
    "product_brand": {
        # exact keys (no wildcard) → use make_key("brand", key_name, **kwargs)
        "detail": "product_brand:detail:{id}",
        "stats": "product_brand:stats:{id}",
        # wildcard patterns → use make_pattern("brand", key_name, **kwargs)
        "variants": "product_brand:variants:{id}:{variant_id}",  # for a single variant
        "variants_all": "product_brand:variants:{id}:*",  # wildcard to delete all variants
        "featured": "product_brands:featured:*",  # wildcard listing
        "list": "product_brand:list:*",  # wildcard for all paginated lists
    },
    "product_inventory": {
        "detail": "product_inventory:detail:{id}",
        "price_stats": "product_inventory:price_stats:{id}",
        "stock": "product_inventory:stock:{id}:{variant_id}",
        "stock_all": "product_inventory:stock:{id}:*",  # wildcard for all stock keys of an item
        "list": "product_inventory:list:*",
    },
    "product_watchlist": {
        "user_list": "product_watchlist:user:{id}:items",  # for a single user’s watchlist
        "items_all": "product_watchlist:items:{id}:*",  # wildcard to delete all items of a user
    },
    # Cache configuration in settings
    "product_image": {
        "list": "product_image:list:{product_id}",
        "primary": "product_image:primary:{product_id}",
        "variants": "product_image:variants:{product_id}",
        "variants_all": "product_image:variants:{product_id}:*",  # For invalidation
    },
    "product_detail": {
        "list": "product_detail:list:{product_id}",
        "highlighted": "product_detail:highlighted:{product_id}",
        "template": "product_detail:template:{template_id}",
        "detail_type": "product_detail:type:{detail_type}",
    },
    "product_meta": {
        "detail": "product_meta:detail:{id}",
        "list": "product_meta:list",
        "featured": "product_meta:featured",
        "views_buf": "product_meta:views_buf:{id}",
    },
    # …add new resources here as needed…
}

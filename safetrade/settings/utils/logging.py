import os
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────
# Create a “logs” directory next to this settings file:
# ─────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Create one log path per performance prefix
from .performance import PERFORMANCE_API_PREFIXES

PERFORMANCE_LOG_PATHS = {
    short_name: LOG_DIR / f"{short_name}_performance.log"
    for short_name in PERFORMANCE_API_PREFIXES.values()
}
MONITORING_LOG_PATH = LOG_DIR / "monitoring.log"
ERROR_LOG_PATH = LOG_DIR / "error.log"
INFO_LOG_PATH = LOG_DIR / "info.log"
THROTTLE_LOG_PATH = LOG_DIR / "throttling.log"
SEARCH_LOG_PATH = LOG_DIR / "product_search.log"
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
        "search_file": {
            "class": "logging.FileHandler",
            "filename": str(SEARCH_LOG_PATH),
            "formatter": "verbose",
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
        "product_search": {
            "handlers": ["search_file"],
            "level": "WARNING",
            "propagate": True,
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

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
    "/api/v1/disputes": "disputes",
    "/api/v1/search": "search",
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

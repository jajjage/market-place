import logging
from django.db import connection
from django_redis import get_redis_connection
from django.conf import settings

monitoring_logger = logging.getLogger("monitoring")


def check_database_performance():
    """
    For each regex in settings.PG_TABLE_PATTERNS, query pg_stat_statements for the top
    10 slowest queries whose query text matches that pattern. If mean_time > threshold, log a warning.
    """
    threshold_ms = settings.SLOW_QUERY_MS_THRESHOLD
    patterns = settings.PG_TABLE_PATTERNS

    with connection.cursor() as cursor:
        # Build a single SQL query that matches any of the table patterns
        # e.g. WHERE query ~ 'brands_|inventory_|...'
        regex_union = "|".join([p.strip("^").strip(".*") for p in patterns])
        sql = """
            SELECT query, mean_time, calls, total_time
            FROM pg_stat_statements
            WHERE query ~ %s
            ORDER BY mean_time DESC
            LIMIT 10;
        """
        cursor.execute(sql, [regex_union])
        rows = cursor.fetchall()

    for query_text, mean_time, calls, total_time in rows:
        # mean_time is in milliseconds
        if mean_time > threshold_ms:
            snippet = query_text[:100].replace("\n", " ")
            monitoring_logger.warning(
                f"[DB] Slow query detected: {mean_time:.2f}ms avg over {calls} calls; snippet: {snippet}…"
            )


def check_cache_hit_ratio():
    """
    Retrieve Redis INFO and compute hit ratio. If below threshold, log a warning.
    """
    redis_conn = get_redis_connection("default")
    info = redis_conn.info()
    hits = info.get("keyspace_hits", 0)
    misses = info.get("keyspace_misses", 0)
    total = hits + misses
    ratio = 100.0 * hits / total if total > 0 else 0.0

    threshold = settings.CACHE_HIT_RATIO_THRESHOLD
    if ratio < threshold:
        monitoring_logger.warning(
            f"[Cache] Low hit ratio: {ratio:.1f}% (threshold: {threshold}%)"
        )
    else:
        monitoring_logger.info(f"[Cache] Hit ratio: {ratio:.1f}%")
    return ratio

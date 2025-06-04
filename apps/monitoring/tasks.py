# monitoring/tasks.py

from celery import shared_task
from monitoring.utils import check_database_performance, check_cache_hit_ratio


@shared_task
def periodic_performance_check():
    """
    Celery task to run every X seconds (configured via CELERY_BEAT_SCHEDULE) and log DB + cache stats.
    """
    # Run the 2 checks
    check_database_performance()
    check_cache_hit_ratio()

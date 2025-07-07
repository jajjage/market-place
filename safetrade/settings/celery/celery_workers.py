import os
import multiprocessing

# Get system information
CPU_CORES = multiprocessing.cpu_count()
AVAILABLE_MEMORY_GB = 8  # Adjust based on your server

# Worker configuration based on environment
CELERY_WORKER_CONFIGS = {
    "development": {
        "workers": min(4, CPU_CORES),
        "concurrency": 2,
        "prefetch_multiplier": 1,
        "max_tasks_per_child": 1000,
        "max_memory_per_child": 200000,  # 200MB in KB
    },
    "production": {
        "workers": min(8, CPU_CORES * 2),
        "concurrency": 4,
        "prefetch_multiplier": 4,
        "max_tasks_per_child": 5000,
        "max_memory_per_child": 500000,  # 500MB in KB
    },
    "high_load": {
        "workers": min(16, CPU_CORES * 3),
        "concurrency": 6,
        "prefetch_multiplier": 2,
        "max_tasks_per_child": 2000,
        "max_memory_per_child": 300000,  # 300MB in KB
    },
}


def get_worker_config():
    """Get worker configuration based on environment"""
    env = os.environ.get("CELERY_WORKER_ENV", "development").lower()
    return CELERY_WORKER_CONFIGS.get(env, CELERY_WORKER_CONFIGS["development"])

from .base import *  # noqa: F401, F403

DEBUG = False

# Override Celery settings for testing
CELERY_TASK_ALWAYS_EAGER = True  # Synchronous execution for tests
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Disable beat scheduler for tests
CELERY_BEAT_SCHEDULE = {}

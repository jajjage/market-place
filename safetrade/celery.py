from __future__ import absolute_import, unicode_literals
import os

from celery import Celery

# from datetime import timedelta
# from django.conf import settings
import environ

# Initialize environment variables
env = environ.Env()

# set the default Django settings module for the 'celery' program.
if env("DEBUG") == "True":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safetrade.settings.dev")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safetrade.settings.prod")
    # os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.settings.prod")
# Set the default Django settings module for the 'celery' program.

app = Celery("safetrade")  # worker

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.broker_connection_retry_on_startup = True

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# app.conf.beat_schedule = {
#     "monitoring-periodic-performance-check": {
#         "task": "monitoring.tasks.periodic_performance_check",
#         # run every PERFORMANCE_CHECK_INTERVAL_SECONDS seconds
#         "schedule": timedelta(seconds=settings.PERFORMANCE_CHECK_INTERVAL_SECONDS),
#     },
# }

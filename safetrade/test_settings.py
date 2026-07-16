from .settings.dev import *  # noqa

# Disable Elasticsearch signal processor (use no-op base) to prevent ES calls in tests
ELASTICSEARCH_DSL_SIGNAL_PROCESSOR = "django_elasticsearch_dsl.signals.BaseSignalProcessor"
ELASTICSEARCH_DSL = {"default": {"hosts": []}}

# Run Celery tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True

# Change the throttle rates for testing
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user_login"] = "1000/minute"  # noqa

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"

    def ready(self):
        # Import signals to ensure signal handlers are registered
        import apps.notifications.signals  # noqa: F401

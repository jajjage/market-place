from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        # Import for side effects, such as signal registration or configuration
        import apps.core.spectacular  # noqa F401

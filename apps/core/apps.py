from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        try:
            import apps.core.openapi.spectacular  # noqa: F401
        except ImportError:
            pass

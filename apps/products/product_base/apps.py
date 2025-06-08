from django.apps import AppConfig


class ProductBaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products.product_base"

    def ready(self):
        import apps.products.product_base.signals  # noqa: F401

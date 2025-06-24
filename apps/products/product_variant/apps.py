from django.apps import AppConfig


class ProductVariantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products.product_variant"

    def ready(self):
        # Import signals to ensure they are registered
        try:
            import apps.products.product_variant.signals  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Failed to import signals for product variant app. "
                "Ensure that the signals module exists and is correctly defined."
            ) from e

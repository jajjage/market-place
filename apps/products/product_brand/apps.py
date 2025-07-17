from django.apps import AppConfig


class ProductBrandConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products.product_brand"

    def ready(self):
        # ensures that `products.documents` is imported
        import apps.products.product_brand.documents  # noqa: F401  # imported for side effects
        import apps.products.product_brand.signals  # noqa: F401  # imported for side effects

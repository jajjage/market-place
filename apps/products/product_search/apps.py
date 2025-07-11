from django.apps import AppConfig


class ProductSearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products.product_search"

    def ready(self):
        # ensures that `products.documents` is imported
        import apps.products.product_search.documents  # noqa: F401  # imported for side effects

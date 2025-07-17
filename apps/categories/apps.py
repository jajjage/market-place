from django.apps import AppConfig


class CategoriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.categories"

    def ready(self):
        # ensures that `products.documents` is imported
        import apps.categories.documents  # noqa: F401  # imported for side effects

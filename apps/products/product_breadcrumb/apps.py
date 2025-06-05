from django.apps import AppConfig


class ProductBreadcrumbConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products.product_breadcrumb"

    # def ready(self):
    #     import apps.transactions.signals  # noqa F401

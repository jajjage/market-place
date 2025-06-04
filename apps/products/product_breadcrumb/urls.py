from django.urls import path
from . import views

app_name = "breadcrumbs"

urlpatterns = [
    # Product breadcrumbs
    path(
        "products/<int:product_id>/breadcrumbs/",
        views.get_product_breadcrumbs,
        name="product-breadcrumbs",
    ),
    path(
        "products/<int:product_id>/breadcrumbs/bulk/",
        views.bulk_create_breadcrumbs,
        name="bulk-create-breadcrumbs",
    ),
    path(
        "products/<int:product_id>/breadcrumbs/default/",
        views.create_default_breadcrumbs,
        name="create-default-breadcrumbs",
    ),
    # Individual breadcrumb management
    path(
        "breadcrumbs/<int:breadcrumb_id>/",
        views.update_breadcrumb,
        name="update-breadcrumb",
    ),
    path(
        "breadcrumbs/<int:breadcrumb_id>/delete/",
        views.delete_breadcrumb,
        name="delete-breadcrumb",
    ),
]

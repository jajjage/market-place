from django.urls import path, include

urlpatterns = [
    path("", include("apps.products.product_base.urls")),
    path("", include("apps.products.product_brand.urls")),
    path("", include("apps.products.product_condition.urls")),
    path("", include("apps.products.product_detail.urls")),
    path("", include("apps.products.product_image.urls")),
    path("", include("apps.products.product_inventory.urls")),
    path("", include("apps.products.product_metadata.urls")),
    path("", include("apps.products.product_negotiation.urls")),
    path("", include("apps.products.product_rating.urls")),
    path("", include("apps.products.product_variant.urls")),
    path("", include("apps.products.product_watchlist.urls")),
    path("", include("apps.products.product_search.urls")),
]

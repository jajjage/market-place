from django.contrib import admin
from .models import ProductDetail, ProductDetailTemplate


@admin.register(ProductDetailTemplate)
class ProductDetailTemplateAdmin(admin.ModelAdmin):
    list_display = ["label", "detail_type", "category", "is_required", "display_order"]
    list_filter = ["detail_type", "is_required", "category"]
    search_fields = ["label", "placeholder_text"]
    ordering = ["display_order", "label"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("label", "detail_type", "category", "display_order")},
        ),
        (
            "Configuration",
            {"fields": ("unit", "is_required", "placeholder_text", "validation_regex")},
        ),
    )


@admin.register(ProductDetail)
class ProductDetailAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "label",
        "detail_type",
        "is_highlighted",
        "is_active",
        "display_order",
    ]
    list_filter = ["detail_type", "is_highlighted", "is_active", "created_at"]
    search_fields = ["product__title", "label", "value"]
    ordering = ["product", "display_order", "label"]
    raw_id_fields = ["product", "template"]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("product", "template", "label", "detail_type")},
        ),
        ("Content", {"fields": ("value", "unit", "is_highlighted")}),
        ("Display", {"fields": ("display_order", "is_active")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("product", "template")

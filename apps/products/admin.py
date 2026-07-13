from django.contrib import admin
from .models import InventoryTransaction
from .models import ProductDetail, ProductDetailTemplate
from .models import SearchLog, PopularSearch, SearchAnalytics
from django.contrib import admin

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
@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "product",
        "transaction_type",
        "quantity",
        "new_total",
        "new_available",
        "new_in_escrow",
        "created_by",
        "created_at",
    ]
    list_filter = ["transaction_type", "created_at"]
    search_fields = ["product__title", "notes", "created_by__username"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
    fieldsets = (
        (
            "Transaction Info",
            {"fields": ("product", "transaction_type", "quantity", "notes")},
        ),
        (
            "Previous State",
            {
                "fields": (
                    "previous_total",
                    "previous_available",
                    "previous_in_escrow",
                ),
                "classes": ("collapse",),
            },
        ),
        ("New State", {"fields": ("new_total", "new_available", "new_in_escrow")}),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ["query", "user", "results_count", "response_time", "created_at"]
    list_filter = ["created_at", "results_count"]
    search_fields = ["query", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
@admin.register(PopularSearch)
class PopularSearchAdmin(admin.ModelAdmin):
    list_display = ["query", "search_count", "last_searched"]
    list_filter = ["last_searched"]
    search_fields = ["query"]
    readonly_fields = ["last_searched", "created_at", "updated_at"]
    def has_add_permission(self, request):
        return False
@admin.register(SearchAnalytics)
class SearchAnalyticsAdmin(admin.ModelAdmin):
    list_display = ["date", "total_searches", "unique_users", "avg_response_time"]
    list_filter = ["date"]
    readonly_fields = ["created_at", "updated_at"]
    def has_add_permission(self, request):
        return False
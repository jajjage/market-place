from django.contrib import admin
from .models import InventoryTransaction


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

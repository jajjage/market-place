from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse


from apps.transactions.models import EscrowTransaction, TransactionHistory


class TransactionHistoryInline(admin.TabularInline):
    """
    Inline admin for transaction history showing status change timeline
    """

    model = TransactionHistory
    extra = 0
    readonly_fields = (
        "new_status",
        "previous_status",
        "created_at",
        "created_by",
        "notes",
    )
    fields = ("new_status", "previous_status", "created_at", "created_by", "notes")
    ordering = ("-created_at",)
    can_delete = False
    max_num = 0  # Don't allow adding new history entries via admin

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EscrowTransaction)
class EscrowTransactionAdmin(admin.ModelAdmin):
    """
    Admin interface for escrow transactions with enhanced monitoring features
    """

    list_display = (
        "id",
        "tracking_id",
        "product_name",
        "status_badge",
        "buyer_name",
        "seller_name",
        "amount_display",
        "days_in_status",
        "created_at",
        "auto_transition_info",
    )
    list_filter = ("status", "currency", "is_auto_transition_scheduled")
    search_fields = ("tracking_id", "product__name", "buyer__email", "seller__email")
    readonly_fields = (
        "tracking_id",
        "created_at",
        "updated_at",
        "status_changed_at",
        "days_in_current_status",
        "next_auto_transition_at",
        "time_until_auto_transition",
    )
    fieldsets = (
        (
            "Transaction Details",
            {
                "fields": (
                    "tracking_id",
                    "product",
                    "buyer",
                    "seller",
                    "amount",
                    "currency",
                    "status",
                    "notes",
                )
            },
        ),
        (
            "Shipping Information",
            {"fields": ("tracking_number", "shipping_carrier", "shipping_address")},
        ),
        (
            "Inspection",
            {
                "fields": ("inspection_period_days", "inspection_end_date"),
            },
        ),
        (
            "Automatic Transitions",
            {
                "fields": (
                    "is_auto_transition_scheduled",
                    "auto_transition_type",
                    "next_auto_transition_at",
                    "time_until_auto_transition",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "modified_at",
                    "status_changed_at",
                    "days_in_current_status",
                ),
            },
        ),
    )
    inlines = [TransactionHistoryInline]
    actions = ["cancel_auto_transitions", "expedite_auto_transitions"]

    def get_queryset(self, request):
        """Add annotations or prefetch related objects for better performance"""
        queryset = super().get_queryset(request)
        return queryset.select_related("buyer", "seller", "product")

    def product_name(self, obj):
        """Display product name with link to product admin"""
        if obj.product:
            return obj.product.name
        return "-"

    product_name.short_description = "Product"

    def buyer_name(self, obj):
        """Display buyer name with link to user admin"""
        if obj.buyer:
            return obj.buyer.email
        return "-"

    buyer_name.short_description = "Buyer"

    def seller_name(self, obj):
        """Display seller name with link to user admin"""
        if obj.seller:
            return obj.seller.email
        return "-"

    seller_name.short_description = "Seller"

    def status_badge(self, obj):
        """Display status as a colored badge"""
        status_colors = {
            "initiated": "#6c757d",  # Gray
            "payment_received": "#17a2b8",  # Cyan
            "shipped": "#fd7e14",  # Orange
            "delivered": "#007bff",  # Blue
            "inspection": "#ffc107",  # Yellow
            "disputed": "#dc3545",  # Red
            "completed": "#28a745",  # Green
            "refunded": "#6f42c1",  # Purple
            "cancelled": "#343a40",  # Dark Gray
        }
        color = status_colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def amount_display(self, obj):
        """Format amount with currency"""
        return f"{obj.amount} {obj.currency}"

    amount_display.short_description = "Amount"

    def days_in_status(self, obj):
        """Display how many days the transaction has been in current status"""
        days = obj.days_in_current_status
        if days == 0:
            hours = (timezone.now() - obj.status_changed_at).seconds // 3600
            return f"{hours} hours"
        return f"{days} days"

    days_in_status.short_description = "Time in Status"

    def auto_transition_info(self, obj):
        """Display information about upcoming automatic transitions"""
        if not obj.is_auto_transition_scheduled:
            return "-"

        if obj.next_auto_transition_at:
            time_remaining = obj.time_until_auto_transition
            if time_remaining:
                days = time_remaining.days
                hours = time_remaining.seconds // 3600
                if days > 0:
                    time_str = f"{days}d {hours}h"
                else:
                    time_str = f"{hours}h"

                return format_html(
                    '<span style="color: #007bff;" title="{}">{}→{} in {}</span>',
                    obj.next_auto_transition_at.strftime("%Y-%m-%d %H:%M:%S"),
                    obj.status,
                    obj.auto_transition_type,
                    time_str,
                )
            else:
                return format_html(
                    '<span style="color: #dc3545;">Overdue: {}→{}</span>',
                    obj.status,
                    obj.auto_transition_type,
                )
        return format_html(
            '<span style="color: #6c757d;">{}</span>', obj.auto_transition_type
        )

    auto_transition_info.short_description = "Auto Transition"

    def cancel_auto_transitions(self, request, queryset):
        """Action to cancel scheduled automatic transitions"""
        updated = queryset.filter(is_auto_transition_scheduled=True).update(
            is_auto_transition_scheduled=False,
            auto_transition_type=None,
            next_auto_transition_at=None,
        )

        for transaction in queryset.filter(is_auto_transition_scheduled=True):
            # Create history entry to record cancellation of auto transition
            TransactionHistory.objects.create(
                transaction=transaction,
                status=transaction.status,
                notes=f"Automatic transition cancelled by admin ({request.user.email})",
                created_by=request.user,
            )

        self.message_user(
            request, f"Cancelled automatic transitions for {updated} transactions."
        )

    cancel_auto_transitions.short_description = "Cancel automatic transitions"

    def expedite_auto_transitions(self, request, queryset):
        """Action to expedite scheduled automatic transitions"""
        from apps.transactions.tasks import (
            schedule_auto_inspection,
            schedule_auto_completion,
            auto_refund_disputed_transaction,
        )

        expedited = 0
        for transaction in queryset.filter(is_auto_transition_scheduled=True):
            if transaction.status == "delivered":
                # Immediately schedule the inspection task
                schedule_auto_inspection.apply_async(
                    args=[transaction.id], countdown=10  # Run after 10 seconds
                )
                expedited += 1
            elif transaction.status == "inspection":
                # Immediately schedule the completion task
                schedule_auto_completion.apply_async(
                    args=[transaction.id], countdown=10  # Run after 10 seconds
                )
                expedited += 1
            elif transaction.status == "disputed":
                # Immediately schedule the refund task
                auto_refund_disputed_transaction.apply_async(
                    args=[transaction.id], countdown=10  # Run after 10 seconds
                )
                expedited += 1

            # Create history entry
            TransactionHistory.objects.create(
                transaction=transaction,
                status=transaction.status,
                notes=f"Automatic transition expedited by admin ({request.user.email})",
                created_by=request.user,
            )

        self.message_user(
            request, f"Expedited automatic transitions for {expedited} transactions."
        )

    expedite_auto_transitions.short_description = "Expedite automatic transitions"


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for transaction history
    """

    list_display = (
        "transaction_ref",
        "new_status",
        "previous_status",
        "created_at",
        "created_by_user",
        "notes_preview",
    )
    list_filter = ("new_status", "previous_status", "created_at")
    search_fields = ("transaction__tracking_id", "notes", "created_by__email")
    readonly_fields = (
        "transaction",
        "new_status",
        "previous_status",
        "created_at",
        "created_by",
        "notes",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("transaction", "created_by")

    def transaction_ref(self, obj):
        """Display transaction reference with link"""
        return format_html(
            '<a href="{}">{}</a>',
            reverse(
                "admin:transactions_escrowtransaction_change", args=[obj.transaction.id]
            ),
            obj.transaction.tracking_id,
        )

    transaction_ref.short_description = "Transaction"

    def created_by_user(self, obj):
        """Display user who created the history entry or 'System' if None"""
        if obj.created_by:
            return obj.created_by.email
        return "System"

    created_by_user.short_description = "Created By"

    def notes_preview(self, obj):
        """Display a preview of notes"""
        if len(obj.notes) > 50:
            return f"{obj.notes[:50]}..."
        return obj.notes

    notes_preview.short_description = "Notes"

    def has_add_permission(self, request):
        """Disable adding history entries directly"""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable changing history entries"""
        return False

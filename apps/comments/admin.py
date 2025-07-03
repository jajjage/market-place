from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import UserRating, RatingEligibility


@admin.register(UserRating)
class UserRatingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "rating",
        "from_user_link",
        "to_user_link",
        "transaction_link",
        "is_verified",
        "is_flagged",
        "created_at",
    ]
    list_filter = ["rating", "is_verified", "is_flagged", "is_anonymous", "created_at"]
    search_fields = [
        "from_user__email",
        "to_user__email",
        "transaction__title",
        "comment",
    ]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["from_user", "to_user", "transaction", "moderated_by"]

    fieldsets = (
        (
            "Rating Information",
            {"fields": ("transaction", "from_user", "to_user", "rating", "comment")},
        ),
        ("Status", {"fields": ("is_verified", "is_anonymous", "is_flagged")}),
        (
            "Moderation",
            {
                "fields": ("moderation_notes", "moderated_by", "moderated_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def from_user_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.from_user.id])
        return format_html('<a href="{}">{}</a>', url, obj.from_user.get_full_name())

    from_user_link.short_description = "From User"

    def to_user_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.to_user.id])
        return format_html('<a href="{}">{}</a>', url, obj.to_user.get_full_name())

    to_user_link.short_description = "To User"

    def transaction_link(self, obj):
        url = reverse(
            "admin:transactions_escrowtransaction_change", args=[obj.transaction.id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.transaction.title[:50])

    transaction_link.short_description = "Transaction"

    actions = ["flag_ratings", "unflag_ratings", "verify_ratings"]

    def flag_ratings(self, request, queryset):
        updated = queryset.update(
            is_flagged=True, moderated_by=request.user, moderated_at=timezone.now()
        )
        self.message_user(request, f"{updated} ratings flagged successfully.")

    flag_ratings.short_description = "Flag selected ratings"

    def unflag_ratings(self, request, queryset):
        updated = queryset.update(
            is_flagged=False, moderated_by=request.user, moderated_at=timezone.now()
        )
        self.message_user(request, f"{updated} ratings unflagged successfully.")

    unflag_ratings.short_description = "Unflag selected ratings"

    def verify_ratings(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} ratings verified successfully.")

    verify_ratings.short_description = "Verify selected ratings"


@admin.register(RatingEligibility)
class RatingEligibilityAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "transaction_link",
        "can_rate_from",
        "rating_deadline",
        "is_active_status",
        "reminder_sent",
        "final_reminder_sent",
    ]
    list_filter = ["reminder_sent", "final_reminder_sent", "created_at"]
    search_fields = ["transaction__title", "transaction__buyer__email"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "is_active_status",
        "days_remaining_display",
    ]
    raw_id_fields = ["transaction"]

    def transaction_link(self, obj):
        url = reverse(
            "admin:transactions_escrowtransaction_change", args=[obj.transaction.id]
        )
        return format_html('<a href="{}">{}</a>', url, obj.transaction.title[:50])

    transaction_link.short_description = "Transaction"

    def is_active_status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">Active</span>')
        else:
            return format_html('<span style="color: red;">Inactive</span>')

    is_active_status.short_description = "Status"

    def days_remaining_display(self, obj):
        return f"{obj.days_remaining} days"

    days_remaining_display.short_description = "Days Remaining"

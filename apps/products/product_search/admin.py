from django.contrib import admin
from .models import SearchLog, PopularSearch, SearchAnalytics


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

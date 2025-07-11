from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel

User = get_user_model()


class SearchLog(BaseModel):
    """Log search queries for analytics"""

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_logs",
    )
    query = models.CharField(max_length=255)
    filters = models.JSONField(default=dict, blank=True)
    results_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    response_time = models.FloatField(null=True, blank=True)  # in seconds

    class Meta:
        db_table = "search_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["query"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Search: {self.query} ({self.results_count} results)"


class PopularSearch(BaseModel):
    """Track popular search terms"""

    query = models.CharField(max_length=255, unique=True)
    search_count = models.PositiveIntegerField(default=0)
    last_searched = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "popular_search"
        ordering = ["-search_count", "-last_searched"]
        indexes = [
            models.Index(fields=["query"]),
            models.Index(fields=["search_count"]),
        ]

    def __str__(self):
        return f"{self.query} ({self.search_count} searches)"


class SearchAnalytics(BaseModel):
    """Daily search analytics"""

    date = models.DateField(unique=True)
    total_searches = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)
    top_queries = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "search_analytics"
        ordering = ["-date"]

    def __str__(self):
        return f"Analytics for {self.date}"

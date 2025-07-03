import django_filters
from django.db.models import Q
from apps.comments.models import UserRating


class UserRatingFilter(django_filters.FilterSet):
    rating_min = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")
    date_from = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    date_to = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    has_comment = django_filters.BooleanFilter(method="filter_has_comment")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = UserRating
        fields = ["rating", "is_verified", "is_anonymous"]

    def filter_has_comment(self, queryset, name, value):
        if value:
            return queryset.exclude(comment="")
        return queryset.filter(comment="")

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(comment__icontains=value)
            | Q(from_user__first_name__icontains=value)
            | Q(from_user__last_name__icontains=value)
            | Q(transaction__title__icontains=value)
        )

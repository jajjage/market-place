import django_filters
from apps.disputes.models import Dispute, DisputeStatus, DisputeReason


class DisputeFilter(django_filters.FilterSet):
    """Filter class for disputes"""

    status = django_filters.ChoiceFilter(choices=DisputeStatus.choices)
    reason = django_filters.ChoiceFilter(choices=DisputeReason.choices)
    opened_by = django_filters.NumberFilter(field_name="opened_by__id")
    transaction = django_filters.UUIDFilter(field_name="transaction__id")
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Dispute
        fields = [
            "status",
            "reason",
            "opened_by",
            "transaction",
            "created_after",
            "created_before",
        ]

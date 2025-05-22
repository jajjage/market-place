from django_filters import rest_framework as filters
from django.db.models import Q
from django.contrib.auth import get_user_model

from apps.transactions.models import EscrowTransaction

User = get_user_model()


class TransactionFilter(filters.FilterSet):
    # Search filters
    search = filters.CharFilter(method="filter_search")

    # Status filter
    status = filters.CharFilter(field_name="status", lookup_expr="exact")

    # Date filters
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    updated_after = filters.DateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_before = filters.DateTimeFilter(field_name="updated_at", lookup_expr="lte")

    # Amount range filters
    min_amount = filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = filters.NumberFilter(field_name="amount", lookup_expr="lte")

    # Related model filters
    buyer = filters.ModelChoiceFilter(queryset=User.objects.all())
    seller = filters.ModelChoiceFilter(queryset=User.objects.all())
    buyer_email = filters.CharFilter(field_name="buyer__email", lookup_expr="iexact")
    seller_email = filters.CharFilter(field_name="seller__email", lookup_expr="iexact")

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "tracking_id",
            "status",
            "amount",
            "currency",
            "buyer",
            "seller",
            "created_at",
            "updated_at",
        ]

    def filter_search(self, queryset, name, value):
        """
        Search across tracking_id, product title, buyer email, and seller email
        """
        return queryset.filter(
            Q(tracking_id__icontains=value)
            | Q(product__title__icontains=value)
            | Q(buyer__email__icontains=value)
            | Q(seller__email__icontains=value)
        )

from django_filters import rest_framework as filters
from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model

from apps.products.models.base import Product

User = get_user_model()


class ProductFilter(filters.FilterSet):
    # Price range filters
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")

    # Discount filters
    has_discount = filters.BooleanFilter(method="filter_has_discount")
    min_discount_percentage = filters.NumberFilter(
        method="filter_min_discount_percentage"
    )

    # Date filters
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")
    updated_after = filters.DateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_before = filters.DateTimeFilter(field_name="updated_at", lookup_expr="lte")

    # Text search
    title_contains = filters.CharFilter(field_name="title", lookup_expr="icontains")
    description_contains = filters.CharFilter(
        field_name="description", lookup_expr="icontains"
    )

    # Related model filters
    seller = filters.ModelChoiceFilter(queryset=User.objects.all())
    seller_username = filters.CharFilter(
        field_name="seller__username", lookup_expr="iexact"
    )
    category_name = filters.CharFilter(
        field_name="category__name", lookup_expr="icontains"
    )
    condition_name = filters.CharFilter(
        field_name="condition__name", lookup_expr="iexact"
    )
    views_count = filters.NumberFilter(method="filter_views_count")
    # Popularity filter
    min_views = filters.NumberFilter(field_name="views_count", lookup_expr="gte")

    # JSON field filters
    has_specification = filters.CharFilter(method="filter_has_specification")
    specification_value = filters.CharFilter(method="filter_specification_value")

    # Combined filters
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Product
        fields = [
            "id",
            "title",
            "price",
            "original_price",
            "category",
            "condition",
            "is_active",
            "seller",
            "min_price",
            "max_price",
        ]

    def filter_views_count(self, queryset, name, value):
        return queryset.filter(**{f"{name}__gte": value})

    def filter_has_discount(self, queryset, name, value):
        """Filter products that have a discount (original_price > price)"""
        if value:
            return queryset.filter(
                original_price__isnull=False, original_price__gt=models.F("price")
            )
        return queryset.filter(
            Q(original_price__isnull=True) | Q(original_price__lte=models.F("price"))
        )

    def filter_min_discount_percentage(self, queryset, name, value):
        """Filter products with at least the specified discount percentage"""
        # Calculate discount percentage: (original_price - price) / original_price * 100
        if value is not None:
            return (
                queryset.filter(original_price__isnull=False, original_price__gt=0)
                .annotate(
                    discount_percentage=(
                        (models.F("original_price") - models.F("price"))
                        * 100
                        / models.F("original_price")
                    )
                )
                .filter(discount_percentage__gte=value)
            )
        return queryset

    def filter_has_specification(self, queryset, name, value):
        """Filter products that have a specific key in specifications JSON"""
        lookup = f"specifications__{value}__isnull"
        return queryset.filter(**{lookup: False})

    def filter_specification_value(self, queryset, name, value):
        """
        Filter by specification value
        Format: 'key:value' (e.g., 'color:red')
        """
        if ":" not in value:
            return queryset

        key, val = value.split(":", 1)
        lookup = f"specifications__{key}"
        return queryset.filter(**{lookup: val})

    def filter_search(self, queryset, name, value):
        """
        Search across multiple fields:
        - title
        - description
        - seller username
        - category name
        """
        if not value:
            return queryset

        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(seller__username__icontains=value)
            | Q(category__name__icontains=value)
        ).distinct()

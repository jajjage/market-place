import django_filters
from apps.products.product_brand.models import Brand


class BrandFilter(django_filters.FilterSet):
    """Advanced filtering for brands"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    country = django_filters.CharFilter(
        field_name="country_of_origin", lookup_expr="iexact"
    )
    founded_after = django_filters.NumberFilter(
        field_name="founded_year", lookup_expr="gte"
    )
    founded_before = django_filters.NumberFilter(
        field_name="founded_year", lookup_expr="lte"
    )
    min_products = django_filters.NumberFilter(
        field_name="cached_product_count", lookup_expr="gte"
    )
    min_rating = django_filters.NumberFilter(
        field_name="cached_average_rating", lookup_expr="gte"
    )
    verified = django_filters.BooleanFilter(field_name="is_verified")
    featured = django_filters.BooleanFilter(field_name="is_featured")

    class Meta:
        model = Brand
        fields = ["name", "country", "verified", "featured"]

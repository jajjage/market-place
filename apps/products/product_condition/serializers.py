from decimal import Decimal
from rest_framework import serializers
from apps.core.serializers import TimestampedModelSerializer
from .models import ProductCondition


class ProductConditionListSerializer(TimestampedModelSerializer):
    """Optimized serializer for listing product conditions."""

    products_count = serializers.IntegerField(
        max_value=1000, min_value=1, read_only=True  # Use int for integer fields
    )
    avg_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        read_only=True,
    )

    class Meta:
        model = ProductCondition
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "quality_score",
            "price_factor",
            "display_order",
            "color_code",
            "icon_name",
            "products_count",
            "avg_price",
            "is_active",
            "created_at",
        ]


class ProductConditionDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer with full information."""

    products_count = serializers.IntegerField(
        max_value=1000, min_value=1, read_only=True  # Use int for integer fields
    )
    avg_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        read_only=True,
    )
    avg_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True
    )
    created_by_name = serializers.CharField(
        source="created_by.first_name", read_only=True
    )

    class Meta:
        model = ProductCondition
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "quality_score",
            "price_factor",
            "display_order",
            "color_code",
            "icon_name",
            "products_count",
            "avg_price",
            "avg_rating",
            "is_active",
            "created_by_name",
            "created_at",
            "updated_at",
        ]


class ProductConditionWriteSerializer(TimestampedModelSerializer):
    """Serializer for creating/updating conditions."""

    class Meta:
        model = ProductCondition
        fields = [
            "name",
            "description",
            "quality_score",
            "price_factor",
            "display_order",
            "color_code",
            "icon_name",
            "is_active",
        ]

    def validate_name(self, value):
        """Validate unique name (case insensitive)."""
        queryset = ProductCondition.objects.filter(name__iexact=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                f"A product condition with the name '{value}' already exists."
            )
        return value

    def validate_quality_score(self, value):
        """Validate quality score range."""
        if not 1 <= value <= 10:
            raise serializers.ValidationError("Quality score must be between 1 and 10.")
        return value

    def validate_price_factor(self, value):
        """Validate price factor range."""
        if not 0.1 <= value <= 2.0:
            raise serializers.ValidationError(
                "Price factor must be between 0.1 and 2.0."
            )
        return value


class ProductConditionAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for condition analytics data."""

    total_products = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    avg_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
    )
    price_range = serializers.DictField()
    categories_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    avg_rating = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("100.00"),
        min_value=Decimal("0.00"),  # ✅ Decimal instance
    )
    stock_status = serializers.DictField()

    class Meta:
        model = ProductCondition
        fields = [
            "id",
            "name",
            "quality_score",
            "total_products",
            "avg_price",
            "price_range",
            "categories_count",
            "avg_rating",
            "stock_status",
        ]


class ConditionBulkOrderSerializer(serializers.Serializer):
    """Serializer for bulk updating display order."""

    conditions = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField(
                max_value=1000, min_value=1  # Use int for integer fields
            )
        )
    )

    def validate_conditions(self, value):
        """Validate condition order data."""
        required_fields = {"id", "order"}

        for item in value:
            if not all(field in item for field in required_fields):
                raise serializers.ValidationError(
                    "Each condition must have 'id' and 'order' fields."
                )

        return value

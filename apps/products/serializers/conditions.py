from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from apps.products.models.product_condition import ProductCondition


class ProductConditionListSerializer(TimestampedModelSerializer):
    """Serializer for listing product conditions."""

    products_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductCondition
        fields = [
            "id",
            "name",
            "description",
            "products_count",
            "is_active",
            "created_at",
        ]

    def get_products_count(self, obj):
        """Count products using this condition."""
        return obj.product_set.count()


class ProductConditionDetailSerializer(TimestampedModelSerializer):
    """Detailed serializer for a single product condition."""

    products_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductCondition
        fields = [
            "id",
            "name",
            "description",
            "products_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_products_count(self, obj):
        """Count products using this condition."""
        return obj.product_set.count()


class ProductConditionWriteSerializer(TimestampedModelSerializer):
    """Serializer for creating/updating product conditions."""

    class Meta:
        model = ProductCondition
        fields = ["name", "description", "is_active"]

    def validate_name(self, value):
        """
        Validate that the condition name is unique (case insensitive).
        """
        # Check if this name exists (case insensitive) excluding the current instance
        queryset = ProductCondition.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                f"A product condition with the name '{value}' already exists."
            )

        return value

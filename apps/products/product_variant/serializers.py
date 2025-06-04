from rest_framework import serializers
from .models import (
    ProductVariantType,
    ProductVariantOption,
    ProductVariant,
)


class ProductVariantOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariantOption
        fields = ["id", "value", "slug", "sort_order"]


class ProductVariantTypeSerializer(serializers.ModelSerializer):
    options = ProductVariantOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariantType
        fields = ["id", "name", "slug", "sort_order", "options"]


class ProductVariantSerializer(serializers.ModelSerializer):
    options = ProductVariantOptionSerializer(many=True, read_only=True)
    option_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "price",
            "stock_quantity",
            "is_active",
            "options",
            "option_ids",
        ]

    def create(self, validated_data):
        option_ids = validated_data.pop("option_ids", [])
        variant = super().create(validated_data)

        if option_ids:
            options = ProductVariantOption.objects.filter(id__in=option_ids)
            variant.options.set(options)

        return variant


class ProductVariantMatrixSerializer(serializers.Serializer):
    """Serializer for variant matrix response"""

    variant_types = ProductVariantTypeSerializer(many=True)
    variants = serializers.DictField()

from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from .models import ProductDetail, ProductDetailTemplate


class ProductDetailTemplateSerializer(serializers.ModelSerializer):
    detail_type_display = serializers.CharField(
        source="get_detail_type_display", read_only=True
    )

    class Meta:
        model = ProductDetailTemplate
        fields = [
            "id",
            "detail_type",
            "detail_type_display",
            "label",
            "unit",
            "is_required",
            "placeholder_text",
            "validation_regex",
            "display_order",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    formatted_value = serializers.ReadOnlyField()
    detail_type_display = serializers.CharField(
        source="get_detail_type_display", read_only=True
    )
    template_info = ProductDetailTemplateSerializer(source="template", read_only=True)

    class Meta:
        model = ProductDetail
        fields = [
            "id",
            "detail_type",
            "detail_type_display",
            "label",
            "value",
            "unit",
            "formatted_value",
            "is_highlighted",
            "display_order",
            "template_info",
            "is_active",
        ]

    def validate(self, data):
        # Custom validation based on template if available
        if "template" in self.initial_data:
            try:
                template = ProductDetailTemplate.objects.get(
                    id=self.initial_data["template"]
                )
                if template.validation_regex and data.get("value"):
                    import re

                    if not re.match(template.validation_regex, data["value"]):
                        raise serializers.ValidationError(
                            f"Value doesn't match required pattern for {template.label}"
                        )
            except ProductDetailTemplate.DoesNotExist:
                pass

        return data


class ProductDetailSummarySerializer(TimestampedModelSerializer):
    """Lightweight version for lists and summaries"""

    formatted_value = serializers.ReadOnlyField()

    class Meta:
        model = ProductDetail
        fields = ["id", "label", "formatted_value", "is_highlighted"]


class ProductDetailGroupedSerializer(serializers.Serializer):
    """Groups details by type"""

    detail_type = serializers.CharField()
    detail_type_display = serializers.CharField()
    details = ProductDetailSerializer(many=True)

    def to_representation(self, instance):
        # instance is a tuple of (detail_type, details_list)
        detail_type, details_list = instance
        return {
            "detail_type": detail_type,
            "detail_type_display": dict(ProductDetail.DetailType.choices).get(
                detail_type, detail_type
            ),
            "details": ProductDetailSerializer(details_list, many=True).data,
        }


class ProductDetailBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creation"""

    details = serializers.ListField(child=serializers.DictField(), write_only=True)

    def validate_details(self, value):
        required_fields = ["detail_type", "label", "value"]
        for detail_data in value:
            for field in required_fields:
                if field not in detail_data:
                    raise serializers.ValidationError(
                        f"Missing required field: {field}"
                    )
        return value

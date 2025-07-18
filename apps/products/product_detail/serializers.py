from rest_framework import serializers

from apps.core.serializers import TimestampedModelSerializer
from .models import ProductDetail, ProductDetailTemplate


class ProductDetailTemplateSerializer(TimestampedModelSerializer):
    """Main serializer for ProductDetailTemplate CRUD operations"""

    category_name = serializers.CharField(source="category.name", read_only=True)
    detail_type_display = serializers.CharField(
        source="get_detail_type_display", read_only=True
    )
    usage_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductDetailTemplate
        fields = [
            "id",
            "detail_type",
            "detail_type_display",
            "label",
            "unit",
            "is_required",
            "category",
            "category_name",
            "placeholder_text",
            "validation_regex",
            "display_order",
            "usage_count",
            "applies_to_subcategories",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_usage_count(self, obj) -> int:
        """Get count of active product details using this template"""
        return obj.product_details.filter(is_active=True).count()

    def validate_validation_regex(self, value):
        """Validate that regex pattern is valid"""
        if value:
            import re

            try:
                re.compile(value)
            except re.error:
                raise serializers.ValidationError("Invalid regex pattern")
        return value

    def validate_label(self, value):
        """Ensure label is not empty after stripping whitespace"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Label cannot be empty")
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # Check for duplicate combination during creation
        if not self.instance:  # Creation
            label = attrs["label"]
            category = attrs.get("category")
            detail_type = attrs["detail_type"]

            if ProductDetailTemplate.objects.filter(
                label=label, category=category, detail_type=detail_type
            ).exists():
                raise serializers.ValidationError(
                    "Template with this label, category, and detail type already exists"
                )

        return attrs


class ProductDetailSerializer(serializers.ModelSerializer):
    formatted_value = serializers.ReadOnlyField()
    detail_type_display = serializers.CharField(
        source="get_detail_type_display", read_only=True
    )

    class Meta:
        model = ProductDetail
        ref_name = "ExtendedProductDetail"
        fields = [
            "id",
            "detail_type_display",
            "label",
            "value",
            "unit",
            "formatted_value",
            "is_highlighted",
            "display_order",
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
        required_fields = ["detail_type", "label", "value", "template_id"]
        for detail_data in value:
            for field in required_fields:
                if field not in detail_data:
                    raise serializers.ValidationError(
                        f"Missing required field: {field}"
                    )
        return value


class ProductDetailTemplateCreateSerializer(TimestampedModelSerializer):
    """Simplified serializer for template creation"""

    class Meta:
        model = ProductDetailTemplate
        fields = [
            "detail_type",
            "label",
            "unit",
            "is_required",
            "category",
            "placeholder_text",
            "validation_regex",
            "display_order",
            "applies_to_subcategories",
        ]

    def validate_label(self, value):
        """Ensure label is not empty after stripping whitespace"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Label cannot be empty")
        return value

    def validate_validation_regex(self, value):
        """Validate that regex pattern is valid"""
        if value:
            import re

            try:
                re.compile(value)
            except re.error:
                raise serializers.ValidationError("Invalid regex pattern")
        return value


class ProductDetailTemplateUpdateSerializer(TimestampedModelSerializer):
    """Serializer for template updates with partial validation"""

    class Meta:
        model = ProductDetailTemplate
        fields = [
            "detail_type",
            "label",
            "unit",
            "is_required",
            "category",
            "placeholder_text",
            "validation_regex",
            "display_order",
            "applies_to_subcategories",
        ]

    def validate_label(self, value):
        """Ensure label is not empty after stripping whitespace"""
        if value is not None:
            value = value.strip()
            if not value:
                raise serializers.ValidationError("Label cannot be empty")
        return value

    def validate_validation_regex(self, value):
        """Validate that regex pattern is valid"""
        if value:
            import re

            try:
                re.compile(value)
            except re.error:
                raise serializers.ValidationError("Invalid regex pattern")
        return value

    def validate(self, attrs):
        """Cross-field validation for updates"""
        # Only check duplicates if we're changing identifying fields
        if any(field in attrs for field in ["label", "category", "detail_type"]):
            instance = self.instance
            label = attrs.get("label", instance.label)
            category = attrs.get("category", instance.category)
            detail_type = attrs.get("detail_type", instance.detail_type)

            if (
                ProductDetailTemplate.objects.filter(
                    label=label, category=category, detail_type=detail_type
                )
                .exclude(id=instance.id)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Template with this combination already exists"
                )

        return attrs


class ProductDetailTemplateSummarySerializer(TimestampedModelSerializer):
    """Lightweight serializer for lists and dropdowns"""

    category_name = serializers.CharField(source="category.name", read_only=True)
    detail_type_display = serializers.CharField(
        source="get_detail_type_display", read_only=True
    )

    class Meta:
        model = ProductDetailTemplate
        fields = [
            "id",
            "label",
            "detail_type",
            "detail_type_display",
            "unit",
            "is_required",
            "category",
            "category_name",
            "display_order",
            "placeholder_text",
            "applies_to_subcategories",
        ]


class ProductDetailTemplateBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk template creation"""

    templates = ProductDetailTemplateCreateSerializer(many=True)

    def validate_templates(self, value):
        """Validate that we don't have duplicate templates in the batch"""
        seen_combinations = set()

        for template_data in value:
            combo = (
                template_data["label"],
                template_data.get("category"),
                template_data["detail_type"],
            )

            if combo in seen_combinations:
                raise serializers.ValidationError(
                    f"Duplicate template in batch: {template_data['label']}"
                )

            seen_combinations.add(combo)

        return value

    def create(self, validated_data):
        """This won't be used directly, but required by DRF"""
        pass


class ProductDetailTemplateUsageSerializer(serializers.Serializer):
    """Serializer for template usage information"""

    template_id = serializers.UUIDField()
    active_usage_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    total_usage_count = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    can_delete = serializers.BooleanField()
    products_using = serializers.ListField(
        child=serializers.IntegerField(
            max_value=1000, min_value=1  # Use int for integer fields
        )
    )


class ProductDetailFromTemplateSerializer(serializers.Serializer):
    """Serializer for creating ProductDetail from template"""

    template_id = serializers.UUIDField()
    value = serializers.CharField()
    is_highlighted = serializers.BooleanField(default=False)
    display_order = serializers.IntegerField(
        max_value=1000, min_value=1, required=False  # Use int for integer fields
    )

    def validate_template_id(self, template_id):
        """Validate that template exists and is active"""
        try:
            template = ProductDetailTemplate.objects.get(id=template_id, is_active=True)
            return template_id
        except ProductDetailTemplate.DoesNotExist:
            raise serializers.ValidationError(
                "Template does not exist or is not active"
            )

    def validate_value(self, value):
        """Validate value against template regex if provided"""
        # We'll validate this in the view where we have access to the template
        return value


class ProductDetailBulkCreateFromTemplatesSerializer(serializers.Serializer):
    """Serializer for bulk creating ProductDetails from templates"""

    template_details = serializers.ListField(
        child=ProductDetailFromTemplateSerializer(), min_length=1
    )


class ProductDetailWithTemplateSerializer(ProductDetailSerializer):
    """Extended ProductDetail serializer with template information"""

    template_info = ProductDetailTemplateSerializer(source="template", read_only=True)
    created_from_template = serializers.BooleanField(read_only=True)

    class Meta(ProductDetailSerializer.Meta):
        fields = ProductDetailSerializer.Meta.fields + [
            "template_info",
            "created_from_template",
            "template_version",
        ]

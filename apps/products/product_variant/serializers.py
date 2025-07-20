from decimal import Decimal
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.serializers import TimestampedModelSerializer
from apps.products.product_base.models import Product
from .models import (
    ProductVariantType,
    ProductVariantOption,
    ProductVariant,
    ProductVariantImage,
)
from .services import ProductVariantService

import logging

logger = logging.getLogger(__name__)


class ProductVariantTypeBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creating variant types"""

    class VariantTypeSerializer(serializers.Serializer):
        name = serializers.CharField(required=True)
        slug = serializers.CharField(required=True)
        sort_order = serializers.IntegerField(required=False, default=0)
        is_active = serializers.BooleanField(required=False, default=True)
        is_required = serializers.BooleanField(required=False, default=False)
        affects_price = serializers.BooleanField(required=False, default=False)
        affects_inventory = serializers.BooleanField(required=False, default=False)

    types = serializers.ListField(child=VariantTypeSerializer(), min_length=1)


class ProductVariantOptionBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creating variant options"""

    class OptionSerializer(serializers.Serializer):
        value = serializers.CharField(required=True)
        slug = serializers.CharField(required=True)
        display_value = serializers.CharField(
            required=False, allow_null=True, allow_blank=True
        )
        color_code = serializers.CharField(
            required=False, allow_null=True, allow_blank=True
        )
        price_adjustment = serializers.DecimalField(
            max_digits=10, decimal_places=2, required=False, default=Decimal("0.00")
        )
        sort_order = serializers.IntegerField(required=False, default=0)
        is_active = serializers.BooleanField(required=False, default=True)
        variant_type_slug = serializers.CharField(required=False, write_only=True)

    options = serializers.ListField(child=OptionSerializer(), min_length=1)
    variant_type_id = serializers.UUIDField(required=True)


class ProductVariantOptionListSerializer(serializers.ListSerializer):
    """List serializer for bulk operations on variant options"""

    def to_representation(self, data):
        """Optimize the list representation to avoid N+1 queries"""
        # Prefetch all related data in a single query
        iterable = (
            data.prefetch_related("variant_type").all()
            if isinstance(data, models.Manager)
            else data
        )
        return [self.child.to_representation(item) for item in iterable]


class ProductVariantOptionSerializer(TimestampedModelSerializer):
    """Enhanced serializer for product variant options"""

    display_name = serializers.CharField(source="display_value", read_only=True)
    variant_type_name = serializers.CharField(
        source="variant_type.name", read_only=True
    )
    variant_type = serializers.UUIDField(
        write_only=True, required=True, help_text="UUID of the variant type"
    )

    class Meta:
        model = ProductVariantOption
        fields = [
            "id",
            "value",
            "slug",
            "sort_order",
            "display_value",
            "color_code",
            "price_adjustment",
            "is_active",
            "display_name",
            "variant_type",
            "variant_type_name",
        ]
        read_only_fields = ["id", "variant_type_name"]
        list_serializer_class = ProductVariantOptionListSerializer

    def to_representation(self, instance):
        """Optimize single instance representation"""
        ret = super().to_representation(instance)
        # Use display_value if available, otherwise fall back to value
        ret["display_name"] = instance.display_value or instance.value
        return ret

    def create(self, validated_data) -> ProductVariantOption:
        variant_type_uuid = validated_data.pop("variant_type")
        try:
            variant_type = ProductVariantType.objects.get(id=variant_type_uuid)
        except ProductVariantType.DoesNotExist:
            raise serializers.ValidationError(
                {"variant_type": "Invalid variant type UUID"}
            )
        validated_data["variant_type"] = variant_type
        return super().create(validated_data)


class ProductVariantTypeSerializer(TimestampedModelSerializer):
    """Enhanced serializer for product variant types"""

    options = ProductVariantOptionSerializer(many=True, read_only=True)
    option_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductVariantType
        fields = [
            "id",
            "name",
            "slug",
            "sort_order",
            "is_active",
            "is_required",
            "display_type",
            "affects_price",
            "affects_inventory",
            "options",
            "option_count",
        ]
        read_only_fields = ["id", "option_count"]


class ProductVariantImageSerializer(TimestampedModelSerializer):
    """Serializer for variant images"""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariantImage
        fields = ["id", "image", "image_url", "alt_text", "sort_order", "is_primary"]

    def get_image_url(self, obj) -> str | None:
        """Get absolute image URL"""
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ProductVariantListSerializer(serializers.ListSerializer):
    """Optimized list serializer for bulk variant operations"""

    def to_representation(self, data):
        """Optimize list representation to avoid N+1 queries"""
        iterable = data.all() if isinstance(data, models.Manager) else data
        return [self.child.to_representation(item) for item in iterable]


class ProductVariantSerializer(TimestampedModelSerializer):
    """Enhanced serializer for product variants with optimized queries"""

    options = ProductVariantOptionSerializer(many=True, read_only=True)
    images = ProductVariantImageSerializer(many=True, read_only=True)
    final_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    available_quantity = serializers.IntegerField(read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    option_summary = serializers.CharField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "price",
            "final_price",
            "total_inventory",
            "available_quantity",
            "is_active",
            "is_in_stock",
            "is_low_stock",
            "options",
            "images",
            "option_summary",
        ]

    def get_final_price(self, obj) -> str | None:
        """Get final price including option adjustments"""
        final_price = obj.final_price
        return str(final_price) if final_price is not None else None

    def get_available_quantity(self, obj) -> int:
        """Get available quantity (stock - reserved)"""
        logger.info(f"get_available_quantity: {obj.available_quantity}")
        return obj.available_quantity

    def get_is_in_stock(self, obj) -> bool:
        """Check if variant is in stock"""
        return obj.is_in_stock

    def get_is_low_stock(self, obj) -> bool:
        """Check if variant is low on stock"""
        return obj.is_low_stock

    def get_option_summary(self, obj) -> str:
        """Get formatted option summary"""
        return " - ".join(
            [
                f"{opt.variant_type.name}: {opt.display_value or opt.value}"
                for opt in obj.options.all()[:3]
            ]
        )

    def get_dimensions(self, obj) -> dict | None:
        """Get dimensions as a dict"""
        if any([obj.dimensions_length, obj.dimensions_width, obj.dimensions_height]):
            return {
                "length": str(obj.dimensions_length) if obj.dimensions_length else None,
                "width": str(obj.dimensions_width) if obj.dimensions_width else None,
                "height": str(obj.dimensions_height) if obj.dimensions_height else None,
            }
        return None

    def to_representation(self, instance):
        """Optimize single instance representation"""
        ret = super().to_representation(instance)

        # Calculate final_price only if price exists
        if instance.price is not None:
            price_adjustments = sum(
                opt.price_adjustment
                for opt in instance.options.all()
                if opt.variant_type.affects_price
            )
            ret["final_price"] = float(instance.final_price + price_adjustments)

        # Calculate availability
        logger.info(
            f"Calculating final price for variant {instance.id}: {instance.price}"
        )
        ret["available_quantity"] = (
            instance.available_quantity - instance.total_inventory
        )
        ret["is_in_stock"] = ret["available_quantity"] > 0
        ret["is_low_stock"] = instance.total_inventory <= instance.low_stock_threshold

        # Generate option summary
        ret["option_summary"] = " - ".join(
            f"{opt.variant_type.name}: {opt.display_value or opt.value}"
            for opt in instance.options.all()[:3]
        )

        return ret


class ProductVariantCreateSerializer(TimestampedModelSerializer):
    """Serializer for creating product variants"""

    option_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        help_text="List of variant option IDs",
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True
    )

    class Meta:
        model = ProductVariant
        fields = [
            "product",
            "sku",
            "cost_price",
            "low_stock_threshold",
            "is_active",
            "weight",
            "total_inventory",
            "dimensions_length",
            "dimensions_width",
            "dimensions_height",
            "is_digital",
            "is_backorderable",
            "expected_restock_date",
            "option_ids",
        ]
        extra_kwargs = {
            "product": {"required": True},
            "sku": {"required": True},
        }

    def validate_option_ids(self, value) -> list:
        """Validate that all option IDs exist and are active"""
        if not value:
            raise serializers.ValidationError("At least one option is required")

        options = ProductVariantOption.objects.filter(id__in=value, is_active=True)
        if len(options) != len(value):
            existing_ids = set(options.values_list("id", flat=True))
            missing_ids = set(value) - existing_ids
            raise serializers.ValidationError(
                f"Invalid or inactive option IDs: {missing_ids}"
            )

        # Check for unique variant types
        variant_types = [opt.variant_type_id for opt in options]
        if len(set(variant_types)) != len(variant_types):
            raise serializers.ValidationError(
                "Options must belong to different variant types"
            )

        return value

    def validate_sku(self, value) -> str:
        """Validate SKU uniqueness"""
        if ProductVariant.objects.filter(sku=value).exists():
            raise serializers.ValidationError(f"SKU '{value}' already exists")
        return value

    def validate(self, attrs) -> dict:
        """Cross-field validation"""
        # Validate reserved quantity doesn't exceed stock
        stock = attrs.get("total_inventory", 0)
        reserved = attrs.get("in_escrow_inventory", 0)
        if reserved > stock:
            raise serializers.ValidationError(
                "Reserved quantity cannot exceed stock quantity"
            )

        return attrs

    def create(self, validated_data) -> ProductVariant:
        """Create variant using service layer"""
        option_ids = validated_data.pop("option_ids")
        product_id = validated_data.pop("product").id
        sku = validated_data.pop("sku")

        try:
            variant = ProductVariantService.create_variant_combination(
                product_id=product_id,
                option_ids=option_ids,
                sku=sku,
                validate_uniqueness=True,
                **validated_data,
            )
            return variant
        except ValidationError as e:
            raise serializers.ValidationError(str(e))


class ProductVariantBulkCreateSerializer(serializers.Serializer):
    """Serializer for bulk creating variants"""

    product_id = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    async_processing = serializers.BooleanField(default=False, source="async")
    variants = serializers.ListField(
        child=serializers.DictField(), help_text="List of variant data dictionaries"
    )

    def validate_product_id(self, value) -> int:
        """Validate product exists"""
        from apps.products.product_base.models import Product

        try:
            Product.objects.get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with id {value} does not exist")
        return value

    def validate_variants(self, value) -> list:
        """Validate variant data structure"""
        if not value:
            raise serializers.ValidationError("At least one variant is required")

        required_fields = ["sku", "option_combinations"]
        for i, variant in enumerate(value):
            for field in required_fields:
                if field not in variant:
                    raise serializers.ValidationError(
                        f"Variant {i}: '{field}' is required"
                    )

            # Validate option_combinations is a list of integers
            option_ids = variant.get("option_combinations", [])
            if not isinstance(option_ids, list) or not all(
                isinstance(x, int) for x in option_ids
            ):
                raise serializers.ValidationError(
                    f"Variant {i}: 'option_combinations' must be a list of integers"
                )

        return value


class ProductVariantCombinationGeneratorSerializer(serializers.Serializer):
    """Serializer for generating variant combinations"""

    product_id = serializers.UUIDField()
    variant_type_options = serializers.DictField(
        child=serializers.ListField(child=serializers.UUIDField()),
        help_text="Dict mapping variant_type_id to list of option_ids",
    )
    base_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )
    sku_separator = serializers.CharField(default="-", max_length=5)

    def validate_product_id(self, value) -> int:
        """Validate product exists"""
        from apps.products.product_base.models import Product

        try:
            Product.objects.get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with id {value} does not exist")
        return value

    def validate_variant_type_options(self, value) -> None:
        """Validate variant type options structure"""
        if not value:
            raise serializers.ValidationError(
                "At least one variant type with options is required"
            )

        # Validate all keys are integers (variant type IDs)
        try:
            variant_type_ids = [int(k) for k in value.keys()]
        except (ValueError, TypeError):
            raise serializers.ValidationError("All variant type keys must be integers")

        # Validate variant types exist
        existing_types = set(
            ProductVariantType.objects.filter(
                id__in=variant_type_ids, is_active=True
            ).values_list("id", flat=True)
        )

        missing_types = set(variant_type_ids) - existing_types
        if missing_types:
            raise serializers.ValidationError(
                f"Invalid variant type IDs: {missing_types}"
            )

        # Validate option IDs
        all_option_ids = []
        for option_list in value.values():
            if not isinstance(option_list, list):
                raise serializers.ValidationError("Option values must be lists")
            all_option_ids.extend(option_list)

        existing_options = set(
            ProductVariantOption.objects.filter(
                id__in=all_option_ids, is_active=True
            ).values_list("id", flat=True)
        )
        missing_options = set(all_option_ids) - existing_options
        if missing_options:
            raise serializers.ValidationError(f"Invalid option IDs: {missing_options}")


class ProductVariantStockUpdateSerializer(serializers.Serializer):
    """Serializer for bulk stock updates"""

    async_processing = serializers.BooleanField(default=False, source="async")
    stock_updates = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of stock update data: [{'variant_id': 1, 'quantity': 10, 'operation': 'set'}]",
    )

    def validate_stock_updates(self, value):
        """Validate stock update data structure"""
        if not value:
            raise serializers.ValidationError("At least one stock update is required")

        valid_operations = ["set", "add", "subtract"]
        required_fields = ["variant_id", "quantity", "operation"]

        variant_ids = []
        for i, update in enumerate(value):
            # Check required fields
            for field in required_fields:
                if field not in update:
                    raise serializers.ValidationError(
                        f"Stock update {i}: '{field}' is required"
                    )

            # Validate variant_id is integer
            try:
                variant_id = int(update["variant_id"])
                variant_ids.append(variant_id)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Stock update {i}: 'variant_id' must be an integer"
                )

            # Validate quantity is positive integer
            try:
                quantity = int(update["quantity"])
                if quantity < 0:
                    raise serializers.ValidationError(
                        f"Stock update {i}: 'quantity' must be non-negative"
                    )
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Stock update {i}: 'quantity' must be an integer"
                )

            # Validate operation
            if update["operation"] not in valid_operations:
                raise serializers.ValidationError(
                    f"Stock update {i}: 'operation' must be one of {valid_operations}"
                )

        # Validate all variant IDs exist
        existing_variants = set(
            ProductVariant.objects.filter(id__in=variant_ids).values_list(
                "id", flat=True
            )
        )
        missing_variants = set(variant_ids) - existing_variants
        if missing_variants:
            raise serializers.ValidationError(f"Variants not found: {missing_variants}")

        return value


class ProductVariantMatrixSerializer(serializers.Serializer):
    """Serializer for variant matrix data"""

    variant_types = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of variant types with their options",
    )
    variants = serializers.DictField(
        help_text="Dictionary of variant data keyed by variant ID"
    )

    def to_representation(self, instance) -> dict:
        """Custom representation for matrix data"""
        from .serializers import ProductVariantTypeSerializer

        variant_types = instance.get("variant_types", [])
        variants = instance.get("variants", {})

        # Serialize variant types
        variant_type_serializer = ProductVariantTypeSerializer(
            variant_types, many=True, context=self.context
        )

        return {
            "variant_types": variant_type_serializer.data,
            "variants": variants,
            "matrix_info": {
                "total_variants": len(variants),
                "total_combinations": len(variants),
                "variant_types_count": len(variant_types),
            },
        }


class ProductVariantStatsSerializer(serializers.Serializer):
    """Serializer for variant statistics"""

    total_variants = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    active_variants = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    inactive_variants = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    in_stock_variants = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    out_of_stock_variants = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    low_stock_variants = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    total_inventory = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    total_in_escrow_inventory = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    total_available_inventory = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )
    average_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        allow_null=True,
    )
    min_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        allow_null=True,
    )
    max_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("9999999.99"),  # Use Decimal for decimal fields
        min_value=Decimal("0.00"),
        allow_null=True,
    )
    total_value = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        max_value=Decimal("100.00"),  # ✅ Decimal instance
        min_value=Decimal("0.00"),
        allow_null=True,
    )

    # Optional breakdown by variant type
    variant_type_breakdown = serializers.DictField(required=False)

    def to_representation(self, instance) -> dict:
        """Add computed fields to representation"""
        data = super().to_representation(instance)

        # Add percentage calculations
        total = data.get("total_variants", 0)
        if total > 0:
            data["active_percentage"] = round(
                (data.get("active_variants", 0) / total) * 100, 2
            )
            data["in_stock_percentage"] = round(
                (data.get("in_stock_variants", 0) / total) * 100, 2
            )
            data["low_stock_percentage"] = round(
                (data.get("low_stock_variants", 0) / total) * 100, 2
            )
        else:
            data["active_percentage"] = 0
            data["in_stock_percentage"] = 0
            data["low_stock_percentage"] = 0

        return data


class ProductVariantTemplateSerializer(serializers.Serializer):
    """Serializer for variant template data (used in variant_template action)"""

    variant_types = serializers.ListField(
        child=serializers.DictField(), help_text="Available variant types with options"
    )
    total_combinations = serializers.IntegerField(
        max_value=1000,  # Use int for integer fields
        min_value=1,
        help_text="Total possible combinations",
    )
    estimated_storage_mb = serializers.FloatField(
        max_value=5.0,  # Use float for float fields
        min_value=0.0,
        help_text="Estimated storage requirements in MB",
    )
    combination_matrix = serializers.ListField(
        child=serializers.ListField(), help_text="Matrix of all possible combinations"
    )

    def to_representation(self, instance) -> dict:
        """Enhanced representation with additional metadata"""
        data = super().to_representation(instance)

        # Add warnings for large combinations
        total_combinations = data.get("total_combinations", 0)
        if total_combinations > 1000:
            data["warnings"] = [
                f"Large number of combinations ({total_combinations}). Consider using async processing."
            ]
        elif total_combinations > 100:
            data["warnings"] = [
                "Moderate number of combinations. Processing may take some time."
            ]
        else:
            data["warnings"] = []

        # Add performance recommendations
        if total_combinations > 500:
            data["recommendations"] = [
                "Use async processing for bulk operations",
                "Consider chunked processing for better performance",
                "Enable caching for frequently accessed variants",
            ]
        else:
            data["recommendations"] = []

        return data


class ProductVariantValidationSerializer(serializers.Serializer):
    """Serializer for variant combination validation results"""

    is_valid = serializers.BooleanField()
    is_unique = serializers.BooleanField()
    existing_variant_id = serializers.UUIDField(allow_null=True)
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    warnings = serializers.ListField(child=serializers.CharField(), required=False)
    suggested_sku = serializers.CharField(allow_null=True, required=False)
    combination_summary = serializers.CharField(required=False)

    def to_representation(self, instance) -> dict:
        """Add contextual information to validation response"""
        data = super().to_representation(instance)

        # Add action recommendations based on validation result
        if not data.get("is_valid", False):
            data["action"] = "fix_errors"
        elif not data.get("is_unique", True):
            data["action"] = "handle_duplicate"
        else:
            data["action"] = "proceed"

        return data

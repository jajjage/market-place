from rest_framework import serializers

from apps.core.serializers import BreadcrumbSerializer, TimestampedModelSerializer
from apps.core.utils.breadcrumbs import BreadcrumbService

from ..models import Category


class CategoryListSerializer(TimestampedModelSerializer):
    """Basic category info without nested subcategories"""

    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )
    product_count = serializers.IntegerField(read_only=True)
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "parent",
            "parent_name",
            "product_count",
            "children_count",
            "is_active",
        ]


class CategorySummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )


class CategoryDetailDepthSerializer(TimestampedModelSerializer):
    """Category serializer with controlled recursion depth"""

    breadcrumbs = serializers.SerializerMethodField()
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )
    subcategories = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True)
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "parent",
            "parent_name",
            "subcategories",
            "breadcrumbs",
            "product_count",
            "children_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_subcategories(self, obj):
        """Get subcategories with depth control"""
        # Get depth from context, default to 1
        depth = self.context.get("depth", 1)

        # If we've reached max depth, return empty
        if depth <= 0:
            return []

        # Get prefetched subcategories
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "subcategories" in obj._prefetched_objects_cache
        ):
            subcategories = obj.subcategories.all()
        else:
            # This should not happen with proper prefetch
            subcategories = obj.subcategories.all()

        # Create new context with reduced depth
        new_context = self.context.copy()
        new_context["depth"] = depth - 1

        return CategoryDetailSerializer(
            subcategories, many=True, context=new_context
        ).data


class CategoryDetailSerializer(TimestampedModelSerializer):
    """Detailed category with ONE level of subcategories only"""

    breadcrumbs = serializers.SerializerMethodField()
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )
    # Use the simpler serializer for subcategories to avoid infinite recursion
    subcategories = CategoryListSerializer(many=True, read_only=True)
    product_count = serializers.IntegerField(read_only=True)
    children_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "parent",
            "parent_name",
            "subcategories",
            "breadcrumbs",
            "product_count",
            "children_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_breadcrumbs(self, obj) -> list:
        service = BreadcrumbService()
        breadcrumb_data = service.for_category(obj)
        return BreadcrumbSerializer(breadcrumb_data, many=True).data


class CategoryWriteSerializer(TimestampedModelSerializer):
    """Serializer for creating/updating categories."""

    class Meta:
        model = Category
        fields = ["name", "description", "parent", "is_active"]

    def validate_parent(self, value):
        """
        Validate that:
        1. A category cannot be its own parent
        2. A category cannot be a parent of its parent (circular reference)
        """
        # If we're updating an existing category
        if self.instance and value:
            # Check if trying to set itself as parent
            if self.instance.id == value.id:
                raise serializers.ValidationError(
                    "A category cannot be its own parent."
                )

            # Check for circular reference
            parent = value
            while parent:
                if parent.parent and parent.parent.id == self.instance.id:
                    raise serializers.ValidationError(
                        "Circular reference detected in category hierarchy."
                    )
                parent = parent.parent

        return value


class CategoryTreeSerializer(TimestampedModelSerializer):
    """Optimized serializer for category tree representation."""

    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "description", "slug", "is_active", "subcategories"]

    def get_subcategories(self, obj) -> list:
        if hasattr(obj, "prefetched_subcategories"):
            return CategoryTreeSerializer(
                obj.prefetched_subcategories, many=True, context=self.context
            ).data
        return []

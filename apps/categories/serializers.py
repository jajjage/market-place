from rest_framework import serializers

from apps.core.serializers import BreadcrumbSerializer, TimestampedModelSerializer
from apps.core.utils.breadcrumbs import BreadcrumbService

from .models import Category


class CategoryListSerializer(TimestampedModelSerializer):
    """Simple serializer for listing categories."""

    subcategories_count = serializers.IntegerField(
        source="subcategories.count", read_only=True
    )

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "parent",
            "subcategories_count",
            "is_active",
            "created_at",
        ]


class RecursiveField(serializers.Serializer):
    """
    A serializer field that can recursively serialize nested objects.
    Used for category hierarchies.
    """

    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class CategorySummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )
    subcategories = RecursiveField(many=True, read_only=True)

    def get_products_count(self, obj):
        """Get count of products in this category."""
        return obj.products.count()


class CategoryDetailSerializer(TimestampedModelSerializer):
    """
    Detailed category serializer with parent info and recursive subcategories.
    """

    breadcrumbs = serializers.SerializerMethodField()
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, allow_null=True
    )
    subcategories = RecursiveField(many=True, read_only=True)
    products_count = serializers.SerializerMethodField()

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
            "products_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_products_count(self, obj):
        """Get count of products in this category."""
        return obj.products.count()

    def get_breadcrumbs(self, obj):
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


class CategoryBreadcrumbSerializer(TimestampedModelSerializer):
    """Serializer for category breadcrumb navigation."""

    path = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "path"]

    def get_path(self, obj):
        """Build breadcrumb path from root to current category."""
        breadcrumbs = []
        category = obj

        # Build path from current category up to root
        while category:
            breadcrumbs.insert(0, {"id": category.id, "name": category.name})
            category = category.parent

        return breadcrumbs


class CategoryTreeSerializer(TimestampedModelSerializer):
    """Optimized serializer for category tree representation."""

    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "description", "slug", "is_active", "subcategories"]

    def get_subcategories(self, obj):
        if hasattr(obj, "prefetched_subcategories"):
            return CategoryTreeSerializer(
                obj.prefetched_subcategories, many=True, context=self.context
            ).data
        return []

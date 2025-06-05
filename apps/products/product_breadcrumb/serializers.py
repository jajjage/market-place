from rest_framework import serializers
from .models import Breadcrumb


class BreadcrumbSerializer(serializers.ModelSerializer):
    class Meta:
        model = Breadcrumb
        fields = ["id", "name", "href", "order"]  # <-- Key part


class BreadcrumbCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Breadcrumb
        fields = ["name", "href", "order"]  # <-- Key part


class BreadcrumbBulkCreateSerializer(serializers.Serializer):
    breadcrumbs = BreadcrumbCreateSerializer(many=True)

    def create(self, validated_data):
        from .services import BreadcrumbService

        # This part needs adjustment: product_id should be obj and content_type
        # product_id = self.context["product_id"]
        # return BreadcrumbService.bulk_create_breadcrumbs(
        #    product_id, validated_data["breadcrumbs"]
        # )
        # It should become:
        obj = self.context["content_object"]  # Pass the actual object instance
        return BreadcrumbService.bulk_create_breadcrumbs(
            obj, validated_data["breadcrumbs"]
        )

from rest_framework import serializers
from .models import Breadcrumb


class BreadcrumbSerializer(serializers.ModelSerializer):
    class Meta:
        model = Breadcrumb
        fields = ["id", "name", "href", "order"]


class BreadcrumbCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Breadcrumb
        fields = ["name", "href", "order"]


class BreadcrumbBulkCreateSerializer(serializers.Serializer):
    breadcrumbs = BreadcrumbCreateSerializer(many=True)

    def create(self, validated_data):
        from .services import BreadcrumbService

        product_id = self.context["product_id"]
        return BreadcrumbService.bulk_create_breadcrumbs(
            product_id, validated_data["breadcrumbs"]
        )

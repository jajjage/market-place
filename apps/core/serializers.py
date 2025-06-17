from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.products.product_base.models import Product


User = get_user_model()


# Base serializer for DRY timestamp fields
def get_timestamp_fields(model):
    fields = []
    for f in ["created_at", "updated_at"]:
        if hasattr(model, f):
            fields.append(f)
    return fields


class TimestampedModelSerializer(serializers.ModelSerializer):
    class Meta:
        abstract = True

    created_at = serializers.DateTimeField(read_only=True, required=False)
    updated_at = serializers.DateTimeField(read_only=True, required=False)


class UserShortSerializer(serializers.ModelSerializer):
    """Serializer for a short representation of the user."""

    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "first_name", "full_name"]

    def get_full_name(self, obj):
        return obj.get_full_name()


class BreadcrumbSerializer(serializers.Serializer):
    """Serializer for breadcrumb items"""

    id = serializers.CharField()
    name = serializers.CharField()
    href = serializers.CharField(allow_null=True)
    order = serializers.IntegerField()


class ProductSummarySerializer(serializers.ModelSerializer):
    """Minimal product info for negotiation responses"""

    formatted_price = serializers.SerializerMethodField()
    seller_name = serializers.CharField(source="seller.get_full_name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "title", "price", "formatted_price", "seller_name"]

    def get_formatted_price(self, obj):
        return f"${obj.price:,.2f}"

from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.products.product_base.models import Product
from apps.products.product_variant.models import ProductVariant


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

    def get_full_name(self, obj) -> str:
        return obj.get_full_name()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = self.context.get("request", None)
        if user and user.user.is_authenticated:
            # optionally add extra fields for logged-in users
            data["is_me"] = instance == user.user
        return data


class VariantShortSerializer(serializers.ModelSerializer):
    """Serializer for a short representation of the user."""

    class Meta:
        model = ProductVariant
        fields = ["id", "sku", "price"]


class BreadcrumbSerializer(serializers.Serializer):
    """Serializer for breadcrumb items"""

    id = serializers.CharField()
    name = serializers.CharField()
    href = serializers.CharField(allow_null=True)
    order = serializers.IntegerField(
        max_value=1000, min_value=1  # Use int for integer fields
    )


class ProductSummarySerializer(serializers.ModelSerializer):
    """Minimal product info for negotiation responses"""

    formatted_price = serializers.SerializerMethodField()
    seller_name = serializers.CharField(source="seller.get_full_name", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "title", "price", "formatted_price", "seller_name"]

    def get_formatted_price(self, obj) -> str:
        return f"${obj.price:,.2f}"

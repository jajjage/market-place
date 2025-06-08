from rest_framework import serializers
from django.contrib.auth import get_user_model


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


class UserShortSerializer(TimestampedModelSerializer):
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

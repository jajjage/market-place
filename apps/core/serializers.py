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

    class Meta:
        model = get_user_model()
        fields = ["id", "first_name", "first_name", "last_name"]

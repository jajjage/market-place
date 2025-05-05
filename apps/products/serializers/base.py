from rest_framework import serializers


class TimestampedModelSerializer(serializers.ModelSerializer):
    """Adds created_at and updated_at fields to all serializers."""

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        abstract = True

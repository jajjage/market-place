from rest_framework import serializers
from apps.comments.models import UserRating
from apps.core.serializers import TimestampedModelSerializer, get_timestamp_fields


class UserRatingSerializer(TimestampedModelSerializer):
    from_user = serializers.PrimaryKeyRelatedField(read_only=True)
    # to_user = serializers.PrimaryKeyRelatedField(read_only=True)
    # transaction = serializers.PrimaryKeyRelatedField(reread_only=True)

    class Meta:
        model = UserRating
        fields = [
            "id",
            "transaction",
            "from_user",
            "to_user",
            "rating",
            "comment",
        ] + get_timestamp_fields(UserRating)
        read_only_fields = ["id", "created_at"] + get_timestamp_fields(UserRating)

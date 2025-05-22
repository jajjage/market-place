from apps.core.serializers import TimestampedModelSerializer, get_timestamp_fields
from apps.store.models import UserStore


class UserStoreSerializer(TimestampedModelSerializer):
    class Meta:
        model = UserStore
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "banner",
            "description",
            "return_policy",
            "shipping_policy",
            "website",
            "is_active",
        ] + get_timestamp_fields(UserStore)
        read_only_fields = ["id", "slug"] + get_timestamp_fields(UserStore)

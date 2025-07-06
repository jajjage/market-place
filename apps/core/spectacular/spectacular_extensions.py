# apps/core/spectacular_extensions.py
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, OpenApiParameter


class UserScopedViewSet(viewsets.ModelViewSet):
    """
    A ModelViewSet that:
     - looks for `user_id` in the URL
     - makes it available as self.user_id
     - documents the `user_id` path‑param exactly once for all actions
    """

    lookup_url_kwarg = "user_id"

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="UUID of the user to scope this endpoint to",
                required=True,
                type={"type": "string", "format": "uuid"},
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def initial(self, request, *args, **kwargs):
        # DRF calls this before any action method
        self.user_id = kwargs.get(self.lookup_url_kwarg)
        return super().initial(request, *args, **kwargs)

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from apps.comments.api.serializers import RatingDetailSerializer

RATING_GIVEN_SCHEMA = extend_schema(
    summary="List ratings given by authenticated user",
    parameters=[
        OpenApiParameter(
            name="tracking_id",
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description="Tracking ID of the transaction",
        )
    ],
    responses={
        200: OpenApiResponse(
            response=RatingDetailSerializer(many=True),
            description="List of ratings given by the user",
        ),
        401: OpenApiResponse(description="Authentication required"),
    },
)

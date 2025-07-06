from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

# from apps.products.product_negotiation.serializers import (
#     # ProductNegotiationSerializer,
# )
CANCEL_NEGOTIATION = extend_schema(
    parameters=[
        OpenApiParameter(
            name="negotiation_id",
            description="UUID of the PriceNegotiation",
            required=True,
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
        )
    ]
)

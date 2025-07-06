from drf_spectacular.utils import extend_schema, OpenApiResponse
from .serializers import (
    DisputeCreateSerializer,
    DisputeDetailSerializer,
    DisputeResolutionSerializer,
    DisputeListSerializer,
)

DISPUTE_VIEW_SET_SCHEMA = {
    "create": extend_schema(
        summary="Create a new dispute",
        request=DisputeCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=DisputeDetailSerializer,
                description="Dispute created successfully",
            ),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Authentication required"),
        },
    ),
    "retrieve": extend_schema(
        summary="Get dispute details",
        responses={
            200: OpenApiResponse(
                response=DisputeDetailSerializer,
                description="Dispute details",
            ),
            401: OpenApiResponse(description="Authentication required"),
            404: OpenApiResponse(description="Dispute not found"),
        },
    ),
    "list": extend_schema(
        summary="List disputes",
        responses={
            200: OpenApiResponse(
                response=DisputeListSerializer(many=True),
                description="List of disputes",
            ),
            401: OpenApiResponse(description="Authentication required"),
        },
    ),
    "resolve": extend_schema(
        summary="Resolve a dispute (admin only)",
        request=DisputeResolutionSerializer,
        responses={
            200: OpenApiResponse(
                response=DisputeDetailSerializer,
                description="Dispute resolved successfully",
            ),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
    "my_disputes": extend_schema(
        summary="Get current user's disputes",
        responses={
            200: OpenApiResponse(
                response=DisputeListSerializer(many=True),
                description="List of current user's disputes",
            ),
            401: OpenApiResponse(description="Authentication required"),
        },
    ),
    "stats": extend_schema(
        summary="Get dispute statistics (admin only)",
        responses={
            200: OpenApiResponse(
                description="Dispute statistics",
            ),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
}

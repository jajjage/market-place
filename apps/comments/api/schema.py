# apps/comments/api/schema.py

from drf_spectacular.utils import (
    extend_schema,
    # OpenApiExample,
    OpenApiResponse,
    OpenApiParameter,
)
from .serializers import (
    RatingCreateSerializer,
    RatingDetailSerializer,
    RatingListSerializer,
    # RatingEligibilitySerializer,
    BuyerSellerEligibilitySerializer,
    RatingStatsSerializer,
    PendingRatingSerializer,
)

# --- SCHEMAS FOR RatingViewSet ENDPOINTS ---

# POST /ratings/ - Create rating
RATING_CREATE_SCHEMA = extend_schema(
    summary="Create a rating",
    description="Create a rating for a completed transaction.",
    request=RatingCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=RatingDetailSerializer,
            description="Rating created successfully",
        ),
        400: OpenApiResponse(
            description="Invalid input or transaction_id missing",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.create

# GET /ratings/ - List all ratings for authenticated user (received)
RATING_LIST_SCHEMA = extend_schema(
    summary="List ratings received by authenticated user",
    responses={
        200: OpenApiResponse(
            response=RatingListSerializer(many=True),
            description="List of ratings received",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.list

# GET /ratings/{id}/ - Get specific rating detail
RATING_DETAIL_SCHEMA = extend_schema(
    summary="Retrieve rating detail",
    responses={
        200: OpenApiResponse(
            response=RatingDetailSerializer,
            description="Rating detail",
        ),
        404: OpenApiResponse(
            description="Rating not found",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.retrieve

# GET /ratings/eligibility/ - Check rating eligibility
RATING_ELIGIBILITY_SCHEMA = extend_schema(
    summary="Check rating eligibility",
    parameters=[
        OpenApiParameter(
            name="seller_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="UUID of the seller (new approach)",
        ),
        OpenApiParameter(
            name="transaction_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="UUID of the transaction (legacy approach)",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=BuyerSellerEligibilitySerializer,
            description="Eligibility result (seller_id)",
        ),
        400: OpenApiResponse(
            description="Missing or invalid parameters",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.eligibility

# GET /ratings/stats/ - Get user rating stats
RATING_STATS_SCHEMA = extend_schema(
    summary="Get user rating stats",
    parameters=[
        OpenApiParameter(
            name="user_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="User ID to get stats for (defaults to self)",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=RatingStatsSerializer,
            description="Aggregated rating statistics",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.stats

# GET /ratings/pending/ - Get pending ratings for authenticated user
RATING_PENDING_SCHEMA = extend_schema(
    summary="List pending ratings",
    parameters=[
        OpenApiParameter(
            name="limit",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Limit the number of pending ratings returned",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PendingRatingSerializer(many=True),
            description="List of pending ratings",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.pending

# GET /ratings/given/ - Get ratings given by authenticated user
RATING_GIVEN_SCHEMA = extend_schema(
    summary="List ratings given by authenticated user",
    responses={
        200: OpenApiResponse(
            response=RatingDetailSerializer(many=True),
            description="List of ratings given",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.given

# GET /ratings/received/ - Get ratings received by authenticated user
RATING_RECEIVED_SCHEMA = extend_schema(
    summary="List ratings received by authenticated user",
    responses={
        200: OpenApiResponse(
            response=RatingDetailSerializer(many=True),
            description="List of ratings received",
        ),
        401: OpenApiResponse(
            description="Authentication required",
        ),
    },
)
# View: RatingViewSet.received


class RatingSchemas:
    """Schema definitions for Rating API endpoints"""

    LIST_USER_RATINGS = extend_schema(
        operation_id="list_user_ratings",
        tags=["User Ratings"],
        summary="List all ratings for a specific user",
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="UUID of the user whose ratings to fetch",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            ),
            OpenApiParameter(
                name="page",
                description="Page number",
                required=False,
                type=int,
                location=OpenApiParameter.QUERY,
            ),
        ],
        responses={
            200: RatingListSerializer(many=True),
            400: OpenApiResponse(description="Invalid user_id"),
            404: OpenApiResponse(description="User not found or no ratings"),
        },
    )

    RETRIEVE_USER_RATING = extend_schema(
        operation_id="retrieve_user_rating",
        tags=["User Ratings"],
        summary="Retrieve a specific rating for a user",
        parameters=[
            OpenApiParameter(
                name="user_id",
                description="UUID of the user whose rating to fetch",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            ),
            OpenApiParameter(
                name="rating_id",
                description="UUID of the specific rating to fetch",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            ),
        ],
        responses={
            200: RatingDetailSerializer(),
            400: OpenApiResponse(description="Invalid user_id or rating_id"),
            404: OpenApiResponse(description="User or rating not found"),
        },
    )

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.core.views import BaseViewSet
from apps.products.product_rating.utils.pagination import RatingPagination
from .models import ProductRating
from .serializers import (
    CreateRatingSerializer,
    ProductRatingAggregateSerializer,
    ProductRatingsSerializer,
)
from .services import ProductRatingService
from .utils.rate_limiting import (
    RatingRateThrottle,
    RatingVoteHelpfulThrottle,
)


class ProductRatingViewSet(BaseViewSet):
    throttle_classes = [RatingRateThrottle]
    serializer_class = ProductRatingsSerializer
    pagination_class = RatingPagination
    permission_classes = []

    def get_queryset(self):
        product_id = self.request.query_params.get("product_id")
        if product_id:
            return (
                ProductRating.objects.filter(product_id=product_id, is_approved=True)
                .select_related("user")
                .order_by("-created_at")
            )
        return ProductRating.objects.none()

    def get_permissions(self):
        if self.action in ["create", "update_rating", "vote_helpful", "my_ratings"]:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return CreateRatingSerializer
        elif self.action == "aggregate":
            return ProductRatingAggregateSerializer
        return self.serializer_class

    def get_throttles(self):
        if self.action == "vote_helpful":
            throttle_classes = [RatingVoteHelpfulThrottle]
        else:
            throttle_classes = self.throttle_classes
        return [throttle() for throttle in throttle_classes]

    def create(self, request, *args, **kwargs):
        """Create a new rating (requires completed purchase and review text)."""
        product_id = request.data.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CreateRatingSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Check if user can rate this product
                can_rate, error_message = ProductRatingService.can_user_rate_product(
                    product_id=product_id, user_id=request.user.id
                )

                if not can_rate:
                    return self.error_response(
                        message=error_message,
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

                rating = ProductRatingService.add_or_update_rating(
                    product_id=product_id,
                    user_id=request.user.id,
                    rating=serializer.validated_data["rating"],
                    review=serializer.validated_data["review"],
                    title=serializer.validated_data.get("title", ""),
                    is_verified_purchase=True,  # Always true since we verify purchase
                )

                response_serializer = ProductRatingsSerializer(
                    rating, context={"request": request}
                )
                return self.success_response(
                    data=response_serializer.data,
                    status_code=status.HTTP_201_CREATED,
                    message="Rating created successfully",
                )

            except Exception as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

    def list(self, request, *args, **kwargs):
        """Get paginated product ratings with filtering and sorting."""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Get filter parameters
        filter_rating = request.query_params.get("rating")
        sort_by = request.query_params.get("sort", "newest")
        show_verified_only = (
            request.query_params.get("verified_only", "false").lower() == "true"
        )

        try:
            result = ProductRatingService.get_product_ratings(
                product_id=product_id,
                filter_rating=int(filter_rating) if filter_rating else None,
                sort_by=sort_by,
                show_verified_only=show_verified_only,
            )

            return self.success_response(
                data=result,
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"], throttle_classes=[RatingVoteHelpfulThrottle])
    def vote_helpful(self, request, pk=None):
        """Vote on rating helpfulness."""
        is_helpful = request.data.get("is_helpful")
        if is_helpful is None:
            return self.error_response(
                message="is_helpful field is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            created = ProductRatingService.vote_helpfulness(
                rating_id=pk, user_id=request.user.id, is_helpful=bool(is_helpful)
            )
            return self.success_response(
                message="Vote recorded" if created else "Vote updated",
            )
        except ProductRating.DoesNotExist:
            return self.error_response(
                message="Rating not found", status_code=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["get"])
    def aggregate(self, request):
        """Get rating aggregate for a product."""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            aggregate = ProductRatingService.get_rating_aggregate(product_id)
            if aggregate:
                serializer = ProductRatingAggregateSerializer(aggregate)
                return self.success_response(data=serializer.data)
            else:
                # If no aggregate record exists, return zeros
                return self.success_response(
                    data={
                        "average": 0,
                        "count": 0,
                        "verified_count": 0,
                        "breakdown": [],
                        "has_reviews": False,
                    }
                )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def can_rate(self, request):
        """Check if current user can rate a specific product."""
        product_id = request.query_params.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            can_rate, message = ProductRatingService.can_user_rate_product(
                product_id=product_id, user_id=request.user.id
            )

            return self.success_response(
                data={
                    "can_rate": can_rate,
                    "message": message,
                    "has_existing_rating": ProductRating.objects.filter(
                        product_id=product_id, user_id=request.user.id
                    ).exists(),
                }
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_ratings(self, request):
        """Get current user's ratings with pagination."""
        page = int(request.query_params.get("page", 1))
        per_page = min(int(request.query_params.get("per_page", 10)), 50)

        try:
            result = ProductRatingService.get_user_ratings(
                user_id=request.user.id, page=page, per_page=per_page
            )

            serializer = ProductRatingsSerializer(
                result["ratings"], many=True, context={"request": request}
            )

            return self.success_response(
                data={
                    "ratings": serializer.data,
                    "pagination": {
                        "current_page": result["current_page"],
                        "total_pages": result["total_pages"],
                        "total_count": result["total_count"],
                        "has_next": result["has_next"],
                        "has_previous": result["has_previous"],
                    },
                }
            )
        except Exception as e:
            return self.error_response(
                message=str(e), status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["put", "patch"], permission_classes=[IsAuthenticated])
    def update_rating(self, request, pk=None):
        """Update user's own rating."""
        try:
            rating = ProductRating.objects.get(id=pk, user=request.user)
        except ProductRating.DoesNotExist:
            return self.error_response(
                message="Rating not found or you don't have permission to edit it",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        serializer = CreateRatingSerializer(data=request.data)
        if serializer.is_valid():
            try:
                updated_rating = ProductRatingService.update_existing_rating(
                    rating_id=rating.id,
                    rating=serializer.validated_data["rating"],
                    review=serializer.validated_data["review"],
                    title=serializer.validated_data.get("title", ""),
                )

                response_serializer = ProductRatingsSerializer(
                    updated_rating, context={"request": request}
                )
                return self.success_response(
                    data=response_serializer.data, message="Rating updated successfully"
                )
            except Exception as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
        )

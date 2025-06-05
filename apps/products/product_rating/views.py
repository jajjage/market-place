from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOwnerOrReadOnly
from apps.core.views import BaseViewSet
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
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        product_id = self.request.query_params.get("product_id")
        if product_id:
            return (
                ProductRating.objects.filter(product_id=product_id, is_approved=True)
                .select_related("user")
                .order_by("-created_at")
            )
        return ProductRating.objects.none()

    def get_throttles(self):
        if self.action == "vote_helpful":
            throttle_classes = [RatingVoteHelpfulThrottle]
        else:
            throttle_classes = self.throttle_classes
        return [throttle() for throttle in throttle_classes]

    def create(self, request, *args, **kwargs):
        """Create a new rating (or update existing if same user + product)."""
        product_id = request.data.get("product_id")
        if not product_id:
            return self.error_response(
                message="product_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CreateRatingSerializer(data=request.data)
        if serializer.is_valid():
            try:
                rating = ProductRatingService.add_or_update_rating(
                    product_id=int(product_id),
                    user_id=request.user.id,
                    rating=serializer.validated_data["rating"],
                    review=serializer.validated_data.get("review", ""),
                    title=serializer.validated_data.get("title", ""),
                    is_verified_purchase=False,  # or derive from actual purchase history
                )

                response_serializer = ProductRatingsSerializer(
                    rating, context={"request": request}
                )
                return self.success_response(
                    data=response_serializer.data, status_code=status.HTTP_201_CREATED
                )

            except Exception as e:
                return self.error_response(
                    message=str(e), status_code=status.HTTP_400_BAD_REQUEST
                )

        return self.error_response(
            message=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST
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
                rating_id=int(pk), user_id=request.user.id, is_helpful=bool(is_helpful)
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
            return Response(
                {"error": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            aggregate = ProductRatingService.get_rating_aggregate(int(product_id))
            if aggregate:
                serializer = ProductRatingAggregateSerializer(aggregate)
                return self.success_response(data=serializer.data)
            else:
                # If no aggregate record exists, return zeros
                return Response(
                    {
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

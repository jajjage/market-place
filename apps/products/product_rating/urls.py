from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductRatingViewSet

router = DefaultRouter()
router.register(r"ratings", ProductRatingViewSet, basename="product-rating")

urlpatterns = [
    path("", include(router.urls)),
]

# The following endpoints will be available:

"""
Rating API Endpoints for Escrow Platform:

1. GET /api/v1/ratings/?product_id={id}&page=1&per_page=10&sort=newest&verified_only=false&rating=5
   - Get paginated product ratings with filtering and sorting
   - Query parameters:
     * product_id (required): ID of the product
     * page: Page number (default: 1)
     * per_page: Items per page (default: 10, max: 50)
     * sort: newest, oldest, helpful, rating_high, rating_low (default: newest)
     * verified_only: true/false (default: false)
     * rating: 1-5 to filter by specific rating

2. POST /api/v1/ratings/
   - Create a new rating (requires authentication and completed purchase)
   - Body: {
       "product_id": 123,
       "rating": 5,
       "review": "Great product! Very satisfied with my purchase.",
       "title": "Excellent quality"
     }

3. PUT /api/v1/ratings/{id}/update_rating/
   - Update user's own rating (requires authentication)
   - Body: Same as create

4. GET /api/v1/ratings/aggregate/?product_id={id}
   - Get rating aggregate/summary for a product
   - Returns: average, count, breakdown by stars, etc.

5. POST /api/v1/ratings/{id}/vote_helpful/
   - Vote on rating helpfulness (requires authentication)
   - Body: {"is_helpful": true}

6. GET /api/v1/ratings/can_rate/?product_id={id}
   - Check if current user can rate a product (requires authentication)
   - Returns: can_rate status and reason

7. GET /api/v1/ratings/my_ratings/?page=1&per_page=10
   - Get current user's ratings (requires authentication)

8. POST /api/v1/ratings/{id}/flag/
   - Flag a rating for moderation (requires authentication)
   - Body: {"reason": "Spam or inappropriate content"}

9. GET /api/v1/ratings/recent/?limit=10
   - Get recent ratings across platform (admin only)

10. POST /api/v1/ratings/{id}/moderate/
    - Moderate flagged rating (admin/moderator only)
    - Body: {"approve": true}
"""

# # Additional URL patterns for admin/moderation (optional)
# from .views import RatingModerationViewSet

# admin_router = DefaultRouter()
# admin_router.register(
#     r"admin/ratings", RatingModerationViewSet, basename="rating-moderation"
# )

# urlpatterns += [
#     path("api/v1/", include(admin_router.urls)),
# ]

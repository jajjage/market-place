from django.urls import path, include
from rest_framework.routers import SimpleRouter
from apps.comments.api.views import RatingViewSet, UserRatingsViewSet

router = SimpleRouter()
# Use a different prefix for the main rating operations
router.register(r"ratings", RatingViewSet, basename="ratings")

urlpatterns = [
    # Include router URLs with a different prefix or namespace
    path("ratings/", include(router.urls)),
    # User-specific rating endpoints
    path(
        "users/<str:user_id>/ratings/",
        UserRatingsViewSet.as_view({"get": "list"}),
        name="user-ratings-list",
    ),
    path(
        "users/<str:user_id>/ratings/<str:rating_id>/",
        UserRatingsViewSet.as_view({"get": "retrieve"}),
        name="user-ratings-detail",
    ),
]

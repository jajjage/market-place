from rest_framework import permissions
from .services import RatingService


class CanRateTransactionPermission(permissions.BasePermission):
    """Check if user can rate the specific transaction"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Extract transaction_id from query parameters
        seller_id = request.query_params.get("seller_id")
        # Alternative: transaction_id = request.GET.get('transaction_id')

        if not seller_id:
            return False

        eligibility = RatingService.check_buyer_seller_rating_eligibility(
            buyer_id=request.user.id, seller_id=seller_id
        )
        return eligibility["can_rate"]

    message = "You don't have permission to rate this transaction."

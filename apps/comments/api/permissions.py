from rest_framework import permissions
from ..services import RatingService


class CanRateTransactionPermission(permissions.BasePermission):
    """Check if user can rate the specific transaction"""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Check transaction-based rating
        transaction_id = RatingService.get_transaction_id_from_request(request)
        if transaction_id:
            try:
                import uuid
                transaction_id = uuid.UUID(str(transaction_id))
            except (ValueError, TypeError):
                return False

            eligibility = RatingService.check_rating_eligibility(
                transaction_id, request.user
            )
            return eligibility["can_rate"]

        # Fallback to seller_id query parameter
        seller_id = request.query_params.get("seller_id")
        if seller_id:
            try:
                import uuid
                seller_id = uuid.UUID(str(seller_id))
            except (ValueError, TypeError):
                return False

            eligibility = RatingService.check_buyer_seller_rating_eligibility(
                buyer_id=request.user.id, seller_id=seller_id
            )
            return eligibility["can_rate"]

        return False

    message = "You don't have permission to rate this transaction."


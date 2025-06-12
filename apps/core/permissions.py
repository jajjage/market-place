import logging

# from apps.transactions.models import EscrowTransaction
from rest_framework import permissions

from apps.transactions.models import EscrowTransaction

logger = logging.getLogger(__name__)


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    - Staff users can do anything.
    - Everyone else has only SAFE_METHODS.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_staff:
            return True
        return request.method in permissions.SAFE_METHODS


class IsNotProductOwner(permissions.BasePermission):
    """
    Allow POST to /products/{pk}/escrow only if user is authenticated
    AND not the product.seller (unless they’re staff).
    """

    def has_permission(self, request, view):
        # Must be authenticated to even attempt placing in escrow
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # SAFE_METHODS aren’t relevant here, since this is a POST-only action.
        # Staff bypass the check:
        if request.user.is_staff:
            return True

        # Block if the user *is* the seller
        return obj.seller_id != request.user.id


class SellerTransaction(permissions.BasePermission):
    """
    Only allow users who are not the owner (seller) of the product
    to place it in escrow.
    """

    def has_permission(self, request, view):
        # We allow permission check to proceed to object-level
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow staff
        if request.user.is_staff:
            return True
        # Only allow if the user is not the seller
        return obj.seller_id == request.user.id


class BuyerTransaction(permissions.BasePermission):
    """
    Only allow users who are not the owner (seller) of the product
    to place it in escrow.
    """

    def has_permission(self, request, view):
        # We allow permission check to proceed to object-level
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow staff
        if request.user.is_staff:
            return True
        # Only allow if the user is not the seller
        return obj.buyer_id == request.user.id


class IsTransactionParticipantOrStaff(permissions.BasePermission):
    """
    For retrieve/update actions on a transaction:
    - Staff can do anything.
    - Buyer or Seller can view and update only their own transactions.
    """

    def has_object_permission(self, request, view, obj: EscrowTransaction):
        # staff → full access
        if request.user.is_staff:
            return True

        # SAFE_METHODS (GET, HEAD, OPTIONS) allowed for buyer/seller
        if request.method in permissions.SAFE_METHODS:
            return request.user in (obj.buyer, obj.seller)

        # non-safe (POST for update-status) also only if buyer/seller
        return request.user in (obj.buyer, obj.seller)


class IsProductOwnerOrStaff(permissions.BasePermission):
    """
    Custom permission:
      - Anyone can read (SAFE_METHODS).
      - Only the product.seller (owner) or staff users can update or delete.
    """

    def has_permission(self, request, view):
        # Allow read-only methods for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # For write methods, user must be authenticated (further checked in has_object_permission)
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # SAFE_METHODS were already allowed
        if request.method in permissions.SAFE_METHODS:
            return True

        # Staff can do anything
        if request.user.is_staff:
            return True

        # Only the owner (seller) of this product may update or delete
        return obj.seller_id == request.user.id

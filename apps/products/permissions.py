from rest_framework import permissions


class IsSellerAndOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission:
    - SAFE_METHODS (GET, HEAD, OPTIONS): Allow for everyone.
    - POST, PUT, PATCH, DELETE: Only allow if user is authenticated, is a SELLER, and is the owner.
    """

    def has_permission(self, request, view):
        # Allow read-only for everyone
        # if request.method in permissions.SAFE_METHODS:
        #     return True

        # Write permissions: must be authenticated and a SELLER
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "user_type", None) == "SELLER"
        )

    def has_object_permission(self, request, view, obj):
        # Read permissions: allow for everyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions: only owner can modify
        return obj.seller == request.user

from rest_framework import permissions


class DisputePermission(permissions.BasePermission):
    """Custom permission for disputes"""

    def has_permission(self, request, view):
        """Check if user has permission to access disputes"""
        if not request.user.is_authenticated:
            return False

        # Staff can access all disputes
        if request.user.is_staff:
            return True

        # Regular users can only access their own disputes
        return True

    def has_object_permission(self, request, view, obj):
        """Check if user has permission to access specific dispute"""
        if request.user.is_staff:
            return True

        # Users can only access disputes for their transactions
        return request.user in [obj.transaction.buyer, obj.transaction.seller]

from rest_framework import permissions


class DisputePermission(permissions.BasePermission):
    """
    Custom permission to only allow owners of a dispute to see it.
    Staff users are allowed to see all disputes.
    """

    def has_object_permission(self, request, view, obj):
        """
        Check if the user has permission to view the dispute.
        """
        if request.user.is_staff:
            return True
        return (
            obj.transaction.buyer == request.user
            or obj.transaction.seller == request.user
        )
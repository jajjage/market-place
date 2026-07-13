from rest_framework import permissions


class IsAdminOrStaff(permissions.BasePermission):
    """Allow access only to admin or staff users."""

    def has_permission(self, request, view):
        return request.user and (request.user.is_staff or request.user.is_superuser)

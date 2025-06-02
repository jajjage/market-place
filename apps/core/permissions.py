from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class UserTypePermission(permissions.BasePermission):
    """
    Custom permission class to handle different user types and their access levels.

    This permission class enforces:
    1. User authentication
    2. User type validation against allowed types
    3. Object ownership verification (when applicable)

    Usage in views:
        class MyView(APIView):
            permission_classes = [UserTypePermission]
            permission_user_types = ['admin', 'manager']  # Required
            permission_object_user_field = 'owner'  # Optional (defaults to 'user')
            permission_superuser_override = True  # Optional (defaults to True)
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            logger.warning(
                f"Unauthenticated access attempt to {view.__class__.__name__}"
            )
            self.message = "Authentication required."
            return False

        # Superuser override (if enabled)
        if (
            getattr(view, "permission_superuser_override", True)
            and request.user.is_superuser
        ):
            return True

        # Get allowed user types from view class
        allowed_user_types = getattr(view, "permission_user_types", None)

        # If no specific user types are defined, deny access
        if not allowed_user_types:
            logger.error(
                f"View {view.__class__.__name__} is missing required 'permission_user_types' attribute"
            )
            self.message = (
                "Server configuration error: permission_user_types not defined."
            )
            return False

        # Check if user's type is in allowed types
        user_type = getattr(request.user, "user_type", None)
        if not user_type:
            logger.warning(f"User {request.user.first_name} has no user_type attribute")
            self.message = "Your account has no assigned user type."
            return False

        has_permission = user_type in allowed_user_types

        # Log permission denial for auditing
        if not has_permission:
            logger.warning(
                f"Permission denied: User {request.user.first_name} ({user_type}) "
                f"attempted to access {view.__class__.__name__} "
                f"which requires one of {allowed_user_types}"
            )
            self.message = f"This action requires one of these user types: {', '.join(allowed_user_types)}."

        return has_permission

    def has_object_permission(self, request, view, obj):
        # First check basic permission
        if not self.has_permission(request, view):
            return False

        # Superuser override (if enabled)
        if (
            getattr(view, "permission_superuser_override", True)
            and request.user.is_superuser
        ):
            return True

        # If read-only methods and view allows read-only, allow access
        if request.method in permissions.SAFE_METHODS and getattr(
            view, "permission_allow_read_only", False
        ):
            return True

        # Get object-specific user field if defined in view
        obj_user_field = getattr(view, "permission_object_user_field", "user")

        # If object has owner field, check ownership
        if hasattr(obj, obj_user_field):
            is_owner = getattr(obj, obj_user_field) == request.user

            if not is_owner:
                self.message = "You don't have permission to modify this object."
                logger.warning(
                    f"Object permission denied: User {request.user.username} attempted to"
                    f"access/modify object {obj} which they don't own"
                )

            return is_owner

        # Get object-specific user type field if defined
        obj_type_restriction = getattr(view, "permission_object_type_field", None)
        if obj_type_restriction and hasattr(obj, obj_type_restriction):
            allowed_types = getattr(obj, obj_type_restriction, [])
            if (
                isinstance(allowed_types, list)
                and request.user.user_type in allowed_types
            ):
                return True

        # If no specific ownership check is defined, fall back to general permission
        return True


class ReadWriteUserTypePermission(UserTypePermission):
    """
    Extended permission class that allows different user types for read/write operations.

    Usage in views:
        class MyView(APIView):
            permission_classes = [ReadWriteUserTypePermission]
            permission_read_user_types = ['admin', 'manager']
            permission_write_user_types = ['admin', 'manager']
            permission_object_user_field = 'owner'  # Optional (defaults to 'user')
    """

    def has_permission(self, request, view):
        # Superuser override (if enabled)
        if (
            getattr(view, "permission_superuser_override", True)
            and request.user.is_superuser
        ):
            return True

        # For read operations
        if request.method in permissions.SAFE_METHODS:
            view.permission_user_types = getattr(view, "permission_read_user_types", [])
        # For write operations
        else:
            view.permission_user_types = getattr(
                view, "permission_write_user_types", []
            )

        return super().has_permission(request, view)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission class that allows:
    - Read access to any user (including unauthenticated users)
    - Write access only to authenticated users who own the object
    """

    def has_permission(self, request, view):
        # Allow read access for any user (authenticated or not)
        if request.method in permissions.SAFE_METHODS:
            return True
        # Require authentication for write operations
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to authenticated owners
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user is the owner
        return (
            obj == request.user or hasattr(obj, "seller") and obj.seller == request.user
        )

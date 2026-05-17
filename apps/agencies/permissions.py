"""Custom permissions for agency account management."""
from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Allow only authenticated admin users."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or getattr(user, "role", "") == "admin")
        )


class IsAgencyOwner(BasePermission):
    """Allow authenticated agency owners."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", "") == "agency_owner"
            and getattr(user, "agency_id", None)
        )

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(getattr(request.user, "agency_id", None) == obj.id)


class IsAgencyOwnerOrAdmin(BasePermission):
    """Allow agency owners for their agency or platform admins."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, "role", "") == "admin":
            return True
        return bool(
            getattr(user, "role", "") == "agency_owner"
            and getattr(user, "agency_id", None)
        )

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if user.is_staff or getattr(user, "role", "") == "admin":
            return True
        return bool(getattr(user, "agency_id", None) == obj.id)

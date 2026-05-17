"""Permissions for property management APIs."""
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAgencyUser(BasePermission):
    """Allow authenticated agency users or staff to manage properties."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        role = getattr(user, "role", "")
        return role in {"agency_owner", "agency_agent"} or bool(
            getattr(user, "agency_id", None)
        )

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if request.method in SAFE_METHODS:
            return True
        if user.is_staff:
            return True
        user_agency_id = getattr(user, "agency_id", None)
        return bool(user_agency_id and obj.agency_id == user_agency_id)

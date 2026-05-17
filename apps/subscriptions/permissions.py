"""Subscription feature-gating permissions."""
from django.utils import timezone
from rest_framework.permissions import BasePermission


def agency_has_active_plan(agency) -> bool:
    """Return whether an agency has an active or trialing subscription."""
    subscription = getattr(agency, "subscription", None)
    if not subscription:
        return False
    if subscription.status not in {"active", "trialing"}:
        return False
    return subscription.expires_at is None or subscription.expires_at >= timezone.now()


class HasActivePlan(BasePermission):
    """Allow access only to users whose agency has an active plan."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or getattr(user, "role", "") == "admin":
            return True
        agency = getattr(user, "agency", None)
        return bool(agency and agency_has_active_plan(agency))

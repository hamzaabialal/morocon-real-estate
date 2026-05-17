"""Decorators for plan feature gating."""
from functools import wraps

from django.http import JsonResponse

from apps.subscriptions.permissions import agency_has_active_plan


def requires_plan_feature(feature_name):
    """Require the current user's agency subscription plan to include a feature."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            request = args[0] if args and hasattr(args[0], "user") else args[1]
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {"error": "Authentication required.", "code": "AUTH_REQUIRED"},
                    status=401,
                )
            if user.is_staff or getattr(user, "role", "") == "admin":
                return view_func(request, *args, **kwargs)

            agency = getattr(user, "agency", None)
            if not agency or not agency_has_active_plan(agency):
                return JsonResponse(
                    {"error": "An active subscription is required.", "code": "PLAN_REQUIRED"},
                    status=403,
                )

            plan = agency.subscription.plan
            if not getattr(plan, feature_name, False):
                return JsonResponse(
                    {
                        "error": "Your plan does not include this feature.",
                        "code": "FEATURE_NOT_INCLUDED",
                    },
                    status=403,
                )
            return view_func(*args, **kwargs)

        return wrapper

    return decorator

"""Shared analytics helpers."""


def get_client_ip(request) -> str:
    """Return the client IP address from proxy headers or REMOTE_ADDR."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"

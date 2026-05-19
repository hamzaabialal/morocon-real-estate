"""Shared analytics helpers."""

from django.db import transaction


def get_client_ip(request) -> str:
    """Return the client IP address from proxy headers or REMOTE_ADDR."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def create_lead_event(property_obj, agency, phone, source):
    """Create a lead event and queue agency notifications after commit."""
    from apps.analytics.models import LeadEvent
    from celery_tasks.notifications import notify_agency_of_lead

    lead_event = LeadEvent.objects.create(
        property=property_obj,
        agency=agency,
        phone=phone,
        source=source,
    )
    transaction.on_commit(lambda: notify_agency_of_lead.delay(str(lead_event.id)))
    return lead_event

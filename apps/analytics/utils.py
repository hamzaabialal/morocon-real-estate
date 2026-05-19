"""Shared analytics helpers."""

from django.db import transaction


def get_client_ip(request) -> str:
    """Return the client IP address from proxy headers or REMOTE_ADDR."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def create_lead_event(property_obj, agency, phone, source, channel=""):
    """Create a lead event and queue agency notifications after commit."""
    from apps.analytics.models import LeadEvent
    from celery_tasks.notifications import notify_agency_of_lead

    lead_event = LeadEvent.objects.create(
        property=property_obj,
        agency=agency,
        phone=phone,
        source=source,
        channel=normalize_channel(channel),
    )
    transaction.on_commit(lambda: notify_agency_of_lead.delay(str(lead_event.id)))
    return lead_event


KNOWN_CHANNELS = {"instagram", "facebook", "tiktok", "youtube", "whatsapp", "email", "direct", "bio"}


def normalize_channel(value):
    """Lower-case + collapse aliases. Returns '' for unknown/empty."""
    if not value:
        return ""
    v = str(value).strip().lower()
    aliases = {"ig": "instagram", "fb": "facebook", "tt": "tiktok", "yt": "youtube"}
    v = aliases.get(v, v)
    return v if v in KNOWN_CHANNELS else ""


def detect_channel_from_referrer(referrer_url):
    """Fallback channel detection when no utm_source — parse the referrer hostname."""
    if not referrer_url:
        return ""
    from urllib.parse import urlparse
    host = urlparse(referrer_url).netloc.lower()
    if "instagram" in host:
        return "instagram"
    if "facebook" in host or "fb." in host:
        return "facebook"
    if "tiktok" in host:
        return "tiktok"
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    return ""

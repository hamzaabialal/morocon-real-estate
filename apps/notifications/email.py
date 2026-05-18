"""Email notification helpers for agency lead alerts and reports."""
import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def send_lead_notification(agency, property_obj, lead_event) -> bool:
    """Send an email alert when a new lead is created for an agency."""
    if not agency or not agency.email:
        return False
    if not agency_has_lead_notifications(agency):
        return False

    title = property_title(property_obj)
    body = "\n".join(
        [
            f"Property: {title}",
            f"Address: {property_obj.formatted_address or property_obj.main_address or 'N/A'}",
            f"Phone: {mask_phone(lead_event.phone)}",
            f"Source: {lead_event.source}",
            f"Date: {lead_event.created_at:%Y-%m-%d %H:%M}",
        ]
    )

    try:
        sent_count = send_mail(
            subject=f"New lead for {title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agency.email],
            fail_silently=False,
        )
        return sent_count > 0
    except Exception as exc:
        logger.exception("Lead notification email failed for agency %s: %s", agency.id, exc)
        return False


def agency_has_lead_notifications(agency) -> bool:
    """Return whether the agency currently has lead notifications enabled."""
    subscription = getattr(agency, "subscription", None)
    if subscription and subscription.is_active:
        return bool(subscription.plan.has_lead_notifications)
    plan = getattr(agency, "subscription_plan", None)
    return bool(plan and plan.has_lead_notifications)


def property_title(property_obj) -> str:
    """Build a readable title from existing property fields."""
    if property_obj.formatted_address:
        return property_obj.formatted_address
    return f"{property_obj.get_property_category_display()} {property_obj.yakeey_ref}".strip()


def mask_phone(phone) -> str | None:
    """Mask a phone number while keeping the final four digits visible."""
    if not phone:
        return None
    digits = "".join(character for character in phone if character.isdigit())
    return f"****{digits[-4:]}" if len(digits) >= 4 else "****"

"""WhatsApp notification helpers using Twilio's WhatsApp API."""
import logging

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)


def send_whatsapp_notification(phone, message) -> bool:
    """Send a WhatsApp message via Twilio, returning False when unavailable."""
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_number = settings.TWILIO_WHATSAPP_FROM
    if not account_sid or not auth_token or not from_number or not phone:
        logger.info("WhatsApp notification skipped because Twilio settings or phone are missing.")
        return False

    to_number = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
    try:
        response = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            data={"From": from_number, "To": to_number, "Body": message},
            auth=(account_sid, auth_token),
            timeout=30.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.exception("WhatsApp notification failed for %s: %s", phone, exc)
        return False

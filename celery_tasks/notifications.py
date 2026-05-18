"""Celery tasks for lead notifications and weekly agency email reports."""
import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.agencies.models import Agency
from apps.analytics.models import LeadEvent, PropertyClick, PropertyView
from apps.notifications.email import (
    agency_has_lead_notifications,
    property_title,
    send_lead_notification,
)
from apps.notifications.whatsapp import send_whatsapp_notification


logger = logging.getLogger(__name__)


@shared_task
def notify_agency_of_lead(lead_event_id):
    """Notify an agency by email and optionally WhatsApp when a lead is received."""
    try:
        lead_event = LeadEvent.objects.select_related(
            "agency", "agency__subscription_plan", "property"
        ).get(id=lead_event_id)
    except LeadEvent.DoesNotExist:
        logger.warning("LeadEvent %s does not exist.", lead_event_id)
        return {"status": "missing", "lead_event_id": lead_event_id}

    agency = lead_event.agency
    if not agency or not agency_has_lead_notifications(agency):
        return {"status": "skipped", "reason": "lead_notifications_disabled"}

    email_sent = send_lead_notification(agency, lead_event.property, lead_event)
    whatsapp_sent = False
    if agency.whatsapp:
        whatsapp_sent = send_whatsapp_notification(
            agency.whatsapp,
            build_lead_whatsapp_message(lead_event),
        )

    return {
        "status": "sent" if email_sent or whatsapp_sent else "failed",
        "email_sent": email_sent,
        "whatsapp_sent": whatsapp_sent,
    }


@shared_task
def send_weekly_agency_report():
    """Send weekly analytics summaries to paid agencies every Monday."""
    today = timezone.localdate()
    week_start = today - timedelta(days=7)
    previous_start = week_start - timedelta(days=7)
    previous_end = week_start - timedelta(days=1)
    sent = 0
    skipped = 0

    agencies = Agency.objects.filter(email__isnull=False).exclude(email="").select_related(
        "subscription_plan"
    )
    for agency in agencies:
        if not agency_has_paid_plan(agency):
            skipped += 1
            continue

        property_ids = list(agency.properties.values_list("id", flat=True))
        views = PropertyView.objects.filter(
            property_id__in=property_ids, created_at__date__gte=week_start
        ).count()
        clicks = PropertyClick.objects.filter(
            property_id__in=property_ids, created_at__date__gte=week_start
        ).count()
        leads = LeadEvent.objects.filter(
            agency=agency, created_at__date__gte=week_start
        ).count()

        previous_views = PropertyView.objects.filter(
            property_id__in=property_ids,
            created_at__date__gte=previous_start,
            created_at__date__lte=previous_end,
        ).count()
        previous_clicks = PropertyClick.objects.filter(
            property_id__in=property_ids,
            created_at__date__gte=previous_start,
            created_at__date__lte=previous_end,
        ).count()
        previous_leads = LeadEvent.objects.filter(
            agency=agency,
            created_at__date__gte=previous_start,
            created_at__date__lte=previous_end,
        ).count()

        try:
            sent_count = send_mail(
                subject="Your weekly Yakeey performance report",
                message=build_weekly_report_body(
                    agency,
                    views,
                    clicks,
                    leads,
                    previous_views,
                    previous_clicks,
                    previous_leads,
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[agency.email],
                fail_silently=False,
            )
            sent += int(sent_count > 0)
        except Exception as exc:
            logger.exception("Weekly report failed for agency %s: %s", agency.id, exc)

    return {"status": "completed", "sent": sent, "skipped": skipped}


def build_lead_whatsapp_message(lead_event):
    """Build a short WhatsApp alert for a lead event."""
    title = property_title(lead_event.property)
    return (
        f"New Yakeey lead for {title}\n"
        f"Source: {lead_event.source}\n"
        f"Phone: {lead_event.phone or 'N/A'}\n"
        f"Date: {lead_event.created_at:%Y-%m-%d %H:%M}"
    )


def build_weekly_report_body(
    agency,
    views,
    clicks,
    leads,
    previous_views,
    previous_clicks,
    previous_leads,
):
    """Build the weekly analytics email body."""
    return "\n".join(
        [
            f"Hello {agency.name},",
            "",
            "Here is your Yakeey performance summary for the last 7 days:",
            f"Views: {views} ({format_delta(views, previous_views)} vs last week)",
            f"Clicks: {clicks} ({format_delta(clicks, previous_clicks)} vs last week)",
            f"Leads: {leads} ({format_delta(leads, previous_leads)} vs last week)",
            "",
            "Keep your best listings fresh to improve visibility.",
        ]
    )


def format_delta(current, previous):
    """Return a compact previous-period comparison."""
    delta = current - previous
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta}"


def agency_has_paid_plan(agency) -> bool:
    """Return whether an agency is on Starter plan or above."""
    subscription = getattr(agency, "subscription", None)
    if subscription and subscription.is_active:
        return subscription.plan.price_monthly > 0
    plan = getattr(agency, "subscription_plan", None)
    return bool(plan and plan.price_monthly > 0)

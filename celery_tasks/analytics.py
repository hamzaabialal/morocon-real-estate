"""Celery tasks for analytics aggregation."""
from collections import Counter
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.agencies.models import Agency
from apps.analytics.models import AgencyAnalyticsSummary, LeadEvent, PropertyClick, PropertyView


@shared_task
def aggregate_daily_analytics():
    """Aggregate previous-day views, clicks, and leads per agency."""
    target_date = timezone.localdate() - timedelta(days=1)
    summaries = 0

    for agency in Agency.objects.all():
        property_ids = list(agency.properties.values_list("id", flat=True))
        views_qs = PropertyView.objects.filter(
            property_id__in=property_ids,
            created_at__date=target_date,
        )
        clicks_qs = PropertyClick.objects.filter(
            property_id__in=property_ids,
            created_at__date=target_date,
        )
        leads_qs = LeadEvent.objects.filter(
            agency=agency,
            created_at__date=target_date,
        )

        top_property_counts = Counter()
        top_property_counts.update(views_qs.values_list("property_id", flat=True))
        top_property_counts.update(clicks_qs.values_list("property_id", flat=True))
        top_property_counts.update(leads_qs.values_list("property_id", flat=True))
        top_property_id = (
            top_property_counts.most_common(1)[0][0] if top_property_counts else None
        )

        AgencyAnalyticsSummary.objects.update_or_create(
            agency=agency,
            date=target_date,
            defaults={
                "views": views_qs.count(),
                "clicks": clicks_qs.count(),
                "leads": leads_qs.count(),
                "top_property_id": top_property_id,
            },
        )
        summaries += 1

    return {"date": target_date.isoformat(), "summaries": summaries}

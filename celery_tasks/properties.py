"""Celery tasks for property maintenance."""
from datetime import timedelta

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from apps.analytics.models import PropertyView
from apps.properties.models import Property


@shared_task
def update_property_views_count(property_id):
    """Recalculate a property's denormalized views_count from tracked views."""
    views_count = PropertyView.objects.filter(property_id=property_id).count()
    updated = Property.objects.filter(id=property_id).update(views_count=views_count)
    return {"property_id": str(property_id), "views_count": views_count, "updated": updated}


@shared_task
def archive_stale_listings():
    """Archive listings that have not been updated in the last 90 days."""
    cutoff = timezone.now() - timedelta(days=90)
    updated = Property.objects.filter(status="LISTED", updated_at__lt=cutoff).update(
        status="ARCHIVED"
    )
    return {"archived": updated, "cutoff": cutoff.isoformat()}


@shared_task
def reindex_search():
    """Placeholder for future Elasticsearch/OpenSearch indexing integration."""
    return {"status": "placeholder", "indexed": 0}

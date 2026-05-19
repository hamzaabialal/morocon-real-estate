"""Signal handlers wired by PropertiesConfig.ready()."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.properties.models import Property


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Property)
def trigger_media_generation_on_create(sender, instance, created, **kwargs):
    """When a new Property lands, queue media generation.

    The media task itself owns cover resolution (AI via DALL-E first, then
    placeholder fallback). The signal stays small and side-effect free.
    """
    if not created or instance.media_status != "pending":
        return

    if getattr(instance, "_skip_media_signal", False):
        return

    try:
        from celery_tasks.media import generate_media_for_property
        generate_media_for_property.delay(str(instance.id))
    except Exception:
        logger.exception("Failed to enqueue media generation for property %s", instance.id)
        Property.objects.filter(id=instance.id).update(media_status="failed")

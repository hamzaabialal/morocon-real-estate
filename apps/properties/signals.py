"""Signal handlers wired by PropertiesConfig.ready()."""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.properties.models import Property


logger = logging.getLogger(__name__)

PLACEHOLDER_COVERS = [
    "/assets/property-1-BF0RFkF4.jpg",
    "/assets/property-2-BdNA2aYD.jpg",
    "/assets/property-3-B-fIDnYp.jpg",
    "/assets/property-4-16KWJM64.jpg",
    "/assets/property-5-CgArBAFm.jpg",
    "/assets/property-6-Bg6-I-q8.jpg",
]


@receiver(post_save, sender=Property)
def trigger_media_generation_on_create(sender, instance, created, **kwargs):
    """When a new Property lands, ensure a cover exists then queue media generation."""
    if not created or instance.media_status != "pending":
        return

    if not instance.cover_image_url and not instance.images.exists():
        placeholder = PLACEHOLDER_COVERS[hash(str(instance.id)) % len(PLACEHOLDER_COVERS)]
        Property.objects.filter(id=instance.id).update(cover_image_url=placeholder)
        instance.cover_image_url = placeholder
        logger.info("Auto-assigned placeholder cover %s to property %s", placeholder, instance.id)

    try:
        from celery_tasks.media import generate_media_for_property
        generate_media_for_property.delay(str(instance.id))
    except Exception:
        logger.exception("Failed to enqueue media generation for property %s", instance.id)
        Property.objects.filter(id=instance.id).update(media_status="failed")

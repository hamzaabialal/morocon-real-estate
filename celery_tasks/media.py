"""Celery tasks for property media generation."""
import logging
import shutil
from pathlib import Path

from celery import shared_task
from django.utils import timezone

from apps.media_engine.caption_generator import generate_captions
from apps.media_engine.storage import upload_media_to_s3
from apps.media_engine.video_generator import generate_property_video
from apps.properties.models import Property


logger = logging.getLogger(__name__)


@shared_task
def generate_media_for_property(property_id):
    """Generate captions and videos for one property."""
    property_obj = Property.objects.get(id=property_id)
    property_obj.media_status = "generating"
    property_obj.save(update_fields=["media_status", "updated_at"])

    temp_dir = None
    try:
        captions = generate_captions(property_obj)
        if captions:
            property_obj.caption_fr = captions.get("caption_fr") or ""
            property_obj.caption_ar = captions.get("caption_ar") or ""
            property_obj.caption_hashtags = captions.get("hashtags") or []

        video_paths = generate_property_video(property_obj)
        if not video_paths:
            raise RuntimeError("Video generation did not produce output files.")

        reel_path, square_path = video_paths
        temp_dir = Path(reel_path).parent
        property_obj.reel_url = upload_media_to_s3(
            reel_path, property_obj.id, "reel.mp4"
        )
        property_obj.square_video_url = upload_media_to_s3(
            square_path, property_obj.id, "square.mp4"
        )

        property_obj.media_status = "ready"
        property_obj.media_generated_at = timezone.now()
        property_obj.save(
            update_fields=[
                "caption_fr",
                "caption_ar",
                "caption_hashtags",
                "reel_url",
                "square_video_url",
                "media_status",
                "media_generated_at",
                "updated_at",
            ]
        )
        return {"property_id": str(property_obj.id), "status": "ready"}
    except Exception as exc:
        logger.exception("Media generation failed for property %s", property_id)
        Property.objects.filter(id=property_id).update(media_status="failed")
        return {"property_id": str(property_id), "status": "failed", "error": str(exc)}
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)


@shared_task
def generate_media_batch(limit=50):
    """Queue media generation for pending properties with at least one image."""
    property_ids = list(
        Property.objects.filter(media_status="pending", images__isnull=False)
        .distinct()
        .values_list("id", flat=True)[:limit]
    )
    for property_id in property_ids:
        generate_media_for_property.apply(args=[str(property_id)])
    logger.info("Queued %s properties for media generation.", len(property_ids))
    return {"queued": len(property_ids)}

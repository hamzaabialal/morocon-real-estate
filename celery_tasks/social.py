"""Celery tasks for social media scheduling workflows."""
import logging
from datetime import datetime, time

from celery import shared_task
from django.utils import timezone

from apps.properties.models import Property
from apps.social.facebook import post_to_facebook
from apps.social.instagram import post_to_instagram
from apps.social.models import SocialPost


logger = logging.getLogger(__name__)


@shared_task
def schedule_social_posts():
    """Schedule the day's top ready property videos for social publishing."""
    today = timezone.localdate()
    schedule_times = [time(hour=10), time(hour=13), time(hour=17)]
    properties = (
        Property.objects.filter(media_status="ready")
        .exclude(reel_url__isnull=True)
        .exclude(reel_url="")
        .exclude(social_posts__created_at__date=today)
        .order_by("-views_count", "-updated_at")
        .distinct()[:3]
    )

    scheduled = 0
    for property_obj, schedule_time in zip(properties, schedule_times):
        scheduled_at = timezone.make_aware(
            datetime.combine(today, schedule_time), timezone.get_current_timezone()
        )
        social_post = SocialPost.objects.create(
            property=property_obj,
            platform="instagram",
            status="scheduled",
            scheduled_at=scheduled_at,
        )
        post_property_to_platform.apply_async(args=[str(social_post.id)], eta=scheduled_at)
        scheduled += 1

    return {"status": "scheduled", "scheduled": scheduled}


@shared_task
def post_property_to_platform(social_post_id):
    """Publish a scheduled SocialPost to the platform-specific API."""
    try:
        social_post = SocialPost.objects.select_related("property").get(id=social_post_id)
    except SocialPost.DoesNotExist:
        logger.warning("SocialPost %s does not exist.", social_post_id)
        return {"status": "missing", "social_post_id": social_post_id}

    property_obj = social_post.property
    caption = build_caption(property_obj)
    video_url = property_obj.reel_url or property_obj.square_video_url

    try:
        if social_post.platform == "instagram":
            post_url = post_to_instagram(property_obj, video_url, caption)
        elif social_post.platform == "facebook":
            post_url = post_to_facebook(property_obj, video_url, caption)
        else:
            raise NotImplementedError(
                f"Posting to {social_post.platform} is not implemented yet."
            )

        if not post_url:
            raise RuntimeError("Platform API did not return a post URL.")

        social_post.status = "posted"
        social_post.post_url = post_url
        social_post.posted_at = timezone.now()
        social_post.error_message = ""
        social_post.save(
            update_fields=["status", "post_url", "posted_at", "error_message"]
        )
        return {"status": "posted", "social_post_id": str(social_post.id)}
    except Exception as exc:
        logger.exception("Social post %s failed: %s", social_post.id, exc)
        social_post.status = "failed"
        social_post.error_message = str(exc)
        social_post.save(update_fields=["status", "error_message"])
        return {
            "status": "failed",
            "social_post_id": str(social_post.id),
            "error": str(exc),
        }


def build_caption(property_obj):
    """Build the caption text sent to social platforms."""
    pieces = [property_obj.caption_fr or property_obj.description or ""]
    hashtags = property_obj.caption_hashtags or []
    if hashtags:
        pieces.append(" ".join(hashtags))
    return "\n\n".join(piece for piece in pieces if piece).strip()

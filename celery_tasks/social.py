"""Celery tasks for social media scheduling and publishing."""
import logging
from datetime import datetime, time

from celery import shared_task
from django.utils import timezone

from apps.properties.models import Property
from apps.social.facebook import post_to_facebook
from apps.social.instagram import post_to_instagram
from apps.social.models import SocialPost
from apps.social.tiktok import post_to_tiktok
from apps.social.youtube import post_to_youtube


logger = logging.getLogger(__name__)

PUBLISHERS = {
    "instagram": post_to_instagram,
    "facebook": post_to_facebook,
    "tiktok": post_to_tiktok,
    "youtube": post_to_youtube,
}

# Order: Instagram + Facebook at 10am, TikTok at 1pm, YouTube at 5pm
PLATFORM_SCHEDULE = [
    ("instagram", time(hour=10)),
    ("facebook", time(hour=10)),
    ("tiktok", time(hour=13)),
    ("youtube", time(hour=17)),
]


@shared_task
def schedule_social_posts():
    """Schedule the day's top ready property videos across all 4 platforms."""
    today = timezone.localdate()
    properties = (
        Property.objects.filter(media_status="ready")
        .exclude(reel_url__isnull=True)
        .exclude(reel_url="")
        .exclude(social_posts__created_at__date=today)
        .order_by("-views_count", "-updated_at")
        .distinct()[:3]
    )

    scheduled_count = 0
    for property_obj in properties:
        for platform, slot in PLATFORM_SCHEDULE:
            scheduled_at = timezone.make_aware(
                datetime.combine(today, slot), timezone.get_current_timezone()
            )
            social_post = SocialPost.objects.create(
                property=property_obj,
                platform=platform,
                status="scheduled",
                scheduled_at=scheduled_at,
            )
            post_property_to_platform.apply_async(
                args=[str(social_post.id)], eta=scheduled_at
            )
            scheduled_count += 1

    return {"status": "scheduled", "scheduled": scheduled_count}


@shared_task
def post_property_to_platform(social_post_id):
    """Publish a scheduled SocialPost to its platform's API."""
    try:
        social_post = SocialPost.objects.select_related("property").get(id=social_post_id)
    except SocialPost.DoesNotExist:
        logger.warning("SocialPost %s does not exist.", social_post_id)
        return {"status": "missing", "social_post_id": social_post_id}

    property_obj = social_post.property
    caption = build_caption(property_obj)
    video_url = property_obj.reel_url or property_obj.square_video_url

    publisher = PUBLISHERS.get(social_post.platform)
    if publisher is None:
        social_post.status = "failed"
        social_post.error_message = f"No publisher registered for {social_post.platform}"
        social_post.save(update_fields=["status", "error_message"])
        return {"status": "failed", "error": social_post.error_message}

    try:
        post_url = publisher(property_obj, video_url, caption)
        if not post_url:
            raise RuntimeError(
                f"{social_post.platform} publisher returned None (missing credentials or video URL not reachable)"
            )
        social_post.status = "posted"
        social_post.post_url = post_url
        social_post.posted_at = timezone.now()
        social_post.error_message = ""
        social_post.save(update_fields=["status", "post_url", "posted_at", "error_message"])
        return {"status": "posted", "social_post_id": str(social_post.id), "url": post_url}
    except Exception as exc:
        logger.exception("Social post %s failed: %s", social_post.id, exc)
        social_post.status = "failed"
        social_post.error_message = str(exc)[:500]
        social_post.save(update_fields=["status", "error_message"])
        return {"status": "failed", "social_post_id": str(social_post.id), "error": str(exc)}


def build_caption(property_obj):
    """Compose the caption text sent to each platform."""
    pieces = [property_obj.caption_fr or property_obj.description or ""]
    hashtags = property_obj.caption_hashtags or []
    if hashtags:
        pieces.append(" ".join(hashtags))
    return "\n\n".join(piece for piece in pieces if piece).strip()

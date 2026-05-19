"""Social scheduling + publishing tasks.

Architecture:
  - schedule_posts_for_property(property)    called inline once media is ready
                                             → creates 4 SocialPost rows at next-available slot
  - publish_due_social_posts (hourly beat)   → scans for SocialPost rows whose
                                             scheduled_at has passed and publishes them
  - post_property_to_platform(sp_id)         → publishes one SocialPost (used by the hourly task
                                             AND directly callable for manual retries)
"""
import logging
from datetime import datetime, time, timedelta

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

# Daily slot per platform (Casablanca local time)
PLATFORM_SCHEDULE = [
    ("instagram", time(hour=10)),
    ("facebook", time(hour=10)),
    ("tiktok", time(hour=13)),
    ("youtube", time(hour=17)),
]


def schedule_posts_for_property(property_obj):
    """Create 4 scheduled SocialPost rows (one per platform) for a property.

    Idempotent: if any scheduled posts already exist for this property, skip.
    Each platform gets its next available daily slot:
      - if today's slot is in the future, use today
      - if today's slot has already passed, push to tomorrow
    """
    if SocialPost.objects.filter(property=property_obj, status="scheduled").exists():
        logger.info("Property %s already has scheduled posts; skipping.", property_obj.id)
        return []

    if not (property_obj.reel_url or property_obj.square_video_url):
        logger.warning("Property %s has no video URL; cannot schedule.", property_obj.id)
        return []

    now = timezone.localtime()
    today = now.date()
    created = []
    for platform, slot in PLATFORM_SCHEDULE:
        scheduled_at = timezone.make_aware(
            datetime.combine(today, slot), timezone.get_current_timezone()
        )
        if scheduled_at <= now:
            scheduled_at += timedelta(days=1)
        post = SocialPost.objects.create(
            property=property_obj,
            platform=platform,
            status="scheduled",
            scheduled_at=scheduled_at,
        )
        created.append(post)
        logger.info(
            "Scheduled %s post for property %s at %s",
            platform, property_obj.id, scheduled_at.isoformat(),
        )
    return created


@shared_task
def publish_due_social_posts():
    """Hourly beat: publish any SocialPost whose scheduled_at has arrived."""
    now = timezone.now()
    due = list(
        SocialPost.objects.filter(status="scheduled", scheduled_at__lte=now)
        .select_related("property")
    )
    summary = {"checked": len(due), "posted": 0, "failed": 0}
    for social_post in due:
        result = post_property_to_platform(str(social_post.id))
        if result.get("status") == "posted":
            summary["posted"] += 1
        else:
            summary["failed"] += 1
    logger.info("publish_due_social_posts summary: %s", summary)
    return summary


@shared_task
def post_property_to_platform(social_post_id):
    """Publish one SocialPost to its platform. Idempotent — re-runs are no-ops if already posted."""
    try:
        social_post = SocialPost.objects.select_related("property").get(id=social_post_id)
    except SocialPost.DoesNotExist:
        logger.warning("SocialPost %s does not exist.", social_post_id)
        return {"status": "missing", "social_post_id": social_post_id}

    if social_post.status == "posted":
        return {"status": "already_posted", "social_post_id": social_post_id, "url": social_post.post_url}

    property_obj = social_post.property
    caption = build_caption(property_obj, platform=social_post.platform)
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
                f"{social_post.platform} publisher returned None — "
                "missing credentials or video URL not publicly reachable"
            )
        social_post.status = "posted"
        social_post.post_url = post_url
        social_post.posted_at = timezone.now()
        social_post.error_message = ""
        social_post.save(update_fields=["status", "post_url", "posted_at", "error_message"])
        return {"status": "posted", "social_post_id": str(social_post.id), "url": post_url}
    except Exception as exc:
        logger.exception("SocialPost %s publish failed: %s", social_post.id, exc)
        social_post.status = "failed"
        social_post.error_message = str(exc)[:500]
        social_post.save(update_fields=["status", "error_message"])
        return {"status": "failed", "social_post_id": str(social_post.id), "error": str(exc)}


def build_caption(property_obj, platform="direct"):
    """Compose the caption text sent to a platform, with UTM-attributed property link."""
    from django.conf import settings
    from apps.properties.views import PLATFORM_SHORT_CODES

    pieces = [property_obj.caption_fr or property_obj.description or ""]

    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    if base:
        platform_code = PLATFORM_SHORT_CODES.get(platform, "")
        if property_obj.short_code and platform_code:
            link = f"{base}/p/{property_obj.short_code}?s={platform_code}"
        else:
            link = (
                f"{base}/properties/{property_obj.id}"
                f"?utm_source={platform}&utm_medium=social&utm_campaign=yakeey_reel"
            )
        pieces.append(f"View: {link}")

    hashtags = property_obj.caption_hashtags or []
    if hashtags:
        pieces.append(" ".join(hashtags))

    return "\n\n".join(piece for piece in pieces if piece).strip()

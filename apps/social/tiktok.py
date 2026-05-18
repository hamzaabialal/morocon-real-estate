"""TikTok Content Posting API integration for property reels.

Requires a TikTok for Developers app with the `video.publish` scope, and a
long-lived access token tied to a Business account. The PULL_FROM_URL upload
mode requires the `video_url` to be reachable by TikTok's servers (so dev
videos served from 127.0.0.1 will not work — use R2/S3 or an ngrok tunnel).

Required settings (read from .env):
    TIKTOK_ACCESS_TOKEN     long-lived OAuth access token
"""
import logging

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)
API_BASE = "https://open.tiktokapis.com/v2"


def post_to_tiktok(property_obj, video_url, caption):
    """Publish a property reel to TikTok using PULL_FROM_URL. Returns post URL or None."""
    access_token = getattr(settings, "TIKTOK_ACCESS_TOKEN", "")
    if not access_token or not video_url:
        logger.warning("TikTok posting skipped (missing token or video URL).")
        return None

    if video_url.startswith("/") or "127.0.0.1" in video_url or "localhost" in video_url:
        logger.warning(
            "TikTok rejected: video_url %s is not publicly reachable. "
            "Upload videos to R2/S3 first.",
            video_url,
        )
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    body = {
        "post_info": {
            "title": (caption or "")[:2200],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            init = client.post(
                f"{API_BASE}/post/publish/video/init/",
                headers=headers,
                json=body,
            )
            init.raise_for_status()
            payload = init.json().get("data", {})
            publish_id = payload.get("publish_id")
            if not publish_id:
                logger.error("TikTok init response missing publish_id: %s", init.text)
                return None
            return f"https://www.tiktok.com/publish_id/{publish_id}"
    except httpx.HTTPError as exc:
        logger.exception("TikTok post failed for property %s: %s", property_obj.id, exc)
        return None

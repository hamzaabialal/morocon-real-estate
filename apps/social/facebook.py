"""Meta Graph API helpers for publishing property videos to Facebook.

Two upload paths:
  - file_url: Meta pulls the video from a public URL (production, R2/S3)
  - multipart 'source': we POST the bytes ourselves (dev / no public hosting)

The publisher picks automatically based on whether video_url is publicly
reachable. Local /media/... paths and 127.0.0.1 URLs go via multipart.
"""
import logging
from pathlib import Path

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


def post_to_facebook(property_obj, video_url, caption):
    """Publish a property video to a Facebook Page and return its permalink."""
    page_id = settings.FACEBOOK_PAGE_ID
    access_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    if not page_id or not access_token or not video_url:
        logger.warning("Facebook posting skipped because credentials or video URL are missing.")
        return None

    try:
        with httpx.Client(timeout=300.0) as client:
            video_id = None
            if is_locally_served(video_url):
                video_bytes = read_local_video_bytes(video_url)
                if not video_bytes:
                    logger.error("Facebook: could not read local video at %s", video_url)
                    return None
                response = client.post(
                    f"{GRAPH_API_BASE}/{page_id}/videos",
                    data={"access_token": access_token, "description": caption or ""},
                    files={"source": ("reel.mp4", video_bytes, "video/mp4")},
                )
            else:
                response = client.post(
                    f"{GRAPH_API_BASE}/{page_id}/videos",
                    data={
                        "access_token": access_token,
                        "file_url": video_url,
                        "description": caption or "",
                    },
                )
            if response.status_code >= 400:
                logger.error("Facebook upload %s: %s", response.status_code, response.text[:500])
                response.raise_for_status()
            video_id = response.json().get("id")
            if not video_id:
                logger.error("Facebook video response did not include an id: %s", response.text[:500])
                return None

            permalink_response = client.get(
                f"{GRAPH_API_BASE}/{video_id}",
                params={"fields": "permalink_url", "access_token": access_token},
            )
            permalink_response.raise_for_status()
            permalink = permalink_response.json().get("permalink_url")
            return f"https://www.facebook.com{permalink}" if permalink and permalink.startswith("/") else permalink
    except httpx.HTTPError as exc:
        logger.exception("Facebook post failed for property %s: %s", property_obj.id, exc)
        return None


def is_locally_served(video_url):
    """Return True for URLs Meta's servers can't reach (dev only)."""
    if video_url.startswith("/"):
        return True
    lowered = video_url.lower()
    return "127.0.0.1" in lowered or "localhost" in lowered


def read_local_video_bytes(video_url):
    """Map a /media/... path to disk and return the bytes."""
    if not video_url.startswith("/"):
        return None
    candidate = Path(settings.BASE_DIR) / video_url.lstrip("/")
    if candidate.exists():
        return candidate.read_bytes()
    return None

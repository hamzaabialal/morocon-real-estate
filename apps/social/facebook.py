"""Meta Graph API helpers for publishing property videos to Facebook."""
import logging

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
        with httpx.Client(timeout=120.0) as client:
            video_response = client.post(
                f"{GRAPH_API_BASE}/{page_id}/videos",
                data={
                    "access_token": access_token,
                    "file_url": video_url,
                    "description": caption or "",
                },
            )
            video_response.raise_for_status()
            video_id = video_response.json().get("id")
            if not video_id:
                logger.error("Facebook video response did not include an id.")
                return None

            permalink_response = client.get(
                f"{GRAPH_API_BASE}/{video_id}",
                params={"fields": "permalink_url", "access_token": access_token},
            )
            permalink_response.raise_for_status()
            return permalink_response.json().get("permalink_url")
    except httpx.HTTPError as exc:
        logger.exception("Facebook post failed for property %s: %s", property_obj.id, exc)
        return None

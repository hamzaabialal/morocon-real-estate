"""Meta Graph API helpers for publishing property reels to Instagram."""
import logging

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)
GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


def post_to_instagram(property_obj, video_url, caption):
    """Create and publish an Instagram Reel, returning the permalink when available."""
    access_token = settings.INSTAGRAM_ACCESS_TOKEN
    account_id = settings.INSTAGRAM_ACCOUNT_ID
    if not access_token or not account_id or not video_url:
        logger.warning("Instagram posting skipped because credentials or video URL are missing.")
        return None

    try:
        with httpx.Client(timeout=60.0) as client:
            container_response = client.post(
                f"{GRAPH_API_BASE}/{account_id}/media",
                data={
                    "access_token": access_token,
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption or "",
                },
            )
            container_response.raise_for_status()
            creation_id = container_response.json().get("id")
            if not creation_id:
                logger.error("Instagram Reel container response did not include an id.")
                return None

            publish_response = client.post(
                f"{GRAPH_API_BASE}/{account_id}/media_publish",
                data={"access_token": access_token, "creation_id": creation_id},
            )
            publish_response.raise_for_status()
            media_id = publish_response.json().get("id")
            if not media_id:
                logger.error("Instagram publish response did not include a media id.")
                return None

            permalink_response = client.get(
                f"{GRAPH_API_BASE}/{media_id}",
                params={"fields": "permalink", "access_token": access_token},
            )
            permalink_response.raise_for_status()
            return permalink_response.json().get("permalink")
    except httpx.HTTPError as exc:
        logger.exception("Instagram post failed for property %s: %s", property_obj.id, exc)
        return None

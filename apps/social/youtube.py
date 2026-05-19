"""YouTube Data API v3 integration for property Shorts.

Requires a Google Cloud project with YouTube Data API v3 enabled and OAuth 2.0
credentials. The refresh token is obtained once via a one-time OAuth flow.

Required settings (read from .env):
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN
    YOUTUBE_CHANNEL_ID      (informational, for building the post URL)
"""
import json
import logging

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def post_to_youtube(property_obj, video_url, caption):
    """Upload a property reel to YouTube as a Short. Returns the public URL or None."""
    client_id = getattr(settings, "YOUTUBE_CLIENT_ID", "")
    client_secret = getattr(settings, "YOUTUBE_CLIENT_SECRET", "")
    refresh_token = getattr(settings, "YOUTUBE_REFRESH_TOKEN", "")
    if not (client_id and client_secret and refresh_token and video_url):
        logger.warning("YouTube posting skipped (missing OAuth credentials or video URL).")
        return None

    access_token = exchange_refresh_token(client_id, client_secret, refresh_token)
    if not access_token:
        return None

    video_bytes = fetch_video_bytes(video_url)
    if not video_bytes:
        logger.error("YouTube post skipped: could not fetch video bytes from %s", video_url)
        return None

    title = (caption or property_obj.formatted_address or property_obj.yakeey_ref or "Property")[:100]
    description = (caption or "")[:5000]
    metadata = {
        "snippet": {
            "title": title,
            "description": description + "\n\n#Shorts",
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                UPLOAD_URL,
                params={"uploadType": "multipart", "part": "snippet,status"},
                headers={"Authorization": f"Bearer {access_token}"},
                files={
                    "metadata": ("metadata.json", json.dumps(metadata), "application/json; charset=UTF-8"),
                    "video": ("video.mp4", video_bytes, "video/mp4"),
                },
            )
            if response.status_code >= 400:
                logger.error("YouTube upload %s: %s", response.status_code, response.text[:500])
                response.raise_for_status()
            video_id = response.json().get("id")
            if not video_id:
                logger.error("YouTube upload returned no id: %s", response.text)
                return None
            return f"https://www.youtube.com/shorts/{video_id}"
    except httpx.HTTPError as exc:
        logger.exception("YouTube upload failed for property %s: %s", property_obj.id, exc)
        return None


def exchange_refresh_token(client_id, client_secret, refresh_token):
    """Trade a long-lived refresh token for a short-lived access token."""
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except httpx.HTTPError as exc:
        logger.exception("YouTube token refresh failed: %s", exc)
        return None


def fetch_video_bytes(video_url):
    """Read the video into memory so we can multipart-upload it to YouTube."""
    if video_url.startswith("/"):
        from pathlib import Path
        candidate = Path(settings.MEDIA_ROOT).parent / video_url.lstrip("/")
        if candidate.exists():
            return candidate.read_bytes()
        return None
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(video_url)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError:
        return None

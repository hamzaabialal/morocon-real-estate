"""AI video generation via Replicate (Stable Video Diffusion).

When REPLICATE_API_TOKEN is set, this generates a short cinematic video clip
from the property's cover image — a real AI-rendered video with smooth camera
motion, not just a Ken Burns slideshow.

Pricing: ~$0.04 per 4-second clip with the default svd-xt model
(rates change; see https://replicate.com/pricing).

Required settings (read from .env):
    REPLICATE_API_TOKEN     long-lived API token from replicate.com
    REPLICATE_VIDEO_MODEL   optional, defaults to a known-good SVD model

The function returns a tuple (reel_path, square_path) just like the FFmpeg
generator, so it's a drop-in replacement at the orchestration layer.
"""
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)

REPLICATE_API = "https://api.replicate.com/v1"
DEFAULT_MODEL = "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438"


class ReplicateNotConfigured(Exception):
    """REPLICATE_API_TOKEN is not set — caller should fall back to FFmpeg."""


def generate_ai_video(property_obj):
    """Generate a cinematic AI video clip from the property cover image.

    Returns (reel_path, square_path) — same shape as the FFmpeg generator.
    Raises ReplicateNotConfigured if no token; lets caller pick a fallback.
    """
    token = getattr(settings, "REPLICATE_API_TOKEN", "")
    if not token:
        raise ReplicateNotConfigured()

    image_url = resolve_image_url(property_obj)
    if not image_url:
        logger.warning("Property %s has no usable image; cannot run AI video.", property_obj.id)
        return None

    prediction = create_prediction(token, image_url, property_obj)
    if not prediction:
        return None

    output_url = poll_until_done(token, prediction["id"], timeout_seconds=300)
    if not output_url:
        return None

    temp_dir = Path(tempfile.mkdtemp(prefix=f"ai-video-{property_obj.id}-"))
    raw_path = temp_dir / "raw.mp4"
    reel_path = temp_dir / "reel.mp4"
    square_path = temp_dir / "square.mp4"

    if not download_video(output_url, raw_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    if not transcode_aspects(raw_path, reel_path, square_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    return str(reel_path), str(square_path)


def resolve_image_url(property_obj):
    """Pick the best public image URL to feed the AI model."""
    main = property_obj.images.filter(is_main=True).first()
    if main and main.url and main.url.startswith("http"):
        return main.url
    first = property_obj.images.order_by("order").first()
    if first and first.url and first.url.startswith("http"):
        return first.url
    cover = property_obj.cover_image_url or ""
    if cover.startswith("http"):
        return cover
    if cover.startswith("/assets/"):
        asset_path = Path(settings.BASE_DIR) / "templates" / "assets" / cover[len("/assets/"):]
        if asset_path.exists():
            return upload_to_replicate_file_store(asset_path)
    return None


def upload_to_replicate_file_store(local_path):
    """Replicate accepts data URLs for small files — convert and return one."""
    import base64
    import mimetypes
    mime = mimetypes.guess_type(str(local_path))[0] or "image/jpeg"
    data = base64.b64encode(local_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def create_prediction(token, image_url, property_obj):
    """Kick off a Replicate prediction. Returns the response JSON or None."""
    model = getattr(settings, "REPLICATE_VIDEO_MODEL", "") or DEFAULT_MODEL
    if ":" not in model:
        logger.error("REPLICATE_VIDEO_MODEL must include a version: 'owner/name:version'.")
        return None
    version = model.split(":", 1)[1]
    payload = {
        "version": version,
        "input": {
            "input_image": image_url,
            "frames_per_second": 6,
            "motion_bucket_id": 127,
            "cond_aug": 0.02,
            "sizing_strategy": "maintain_aspect_ratio",
        },
    }
    try:
        response = httpx.post(
            f"{REPLICATE_API}/predictions",
            headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logger.exception("Replicate create_prediction failed: %s", exc)
        return None


def poll_until_done(token, prediction_id, timeout_seconds=300):
    """Block until the prediction is done. Returns the output URL or None."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(
                f"{REPLICATE_API}/predictions/{prediction_id}",
                headers={"Authorization": f"Token {token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Replicate poll failed: %s", exc)
            time.sleep(5)
            continue

        status = data.get("status")
        if status == "succeeded":
            output = data.get("output")
            if isinstance(output, list):
                return output[0] if output else None
            return output
        if status in {"failed", "canceled"}:
            logger.error("Replicate prediction %s ended with %s: %s", prediction_id, status, data.get("error"))
            return None
        time.sleep(3)
    logger.error("Replicate prediction %s timed out after %ss", prediction_id, timeout_seconds)
    return None


def download_video(url, dest):
    """Download the prediction output to a local file."""
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            dest.write_bytes(response.content)
            return True
    except httpx.HTTPError as exc:
        logger.exception("Failed to download AI video: %s", exc)
        return False


def transcode_aspects(raw_path, reel_path, square_path):
    """Re-encode the raw AI output to vertical 9:16 reel and 1:1 square."""
    from apps.media_engine.video_generator import get_ffmpeg_binary

    ffmpeg = get_ffmpeg_binary()
    common_filter = "scale=1080:-2:force_original_aspect_ratio=increase,setsar=1"

    cmds = [
        (
            reel_path,
            f"{common_filter},crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2",
        ),
        (
            square_path,
            f"{common_filter},crop=1080:1080:(in_w-1080)/2:(in_h-1080)/2",
        ),
    ]
    for output_path, vf in cmds:
        result = subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(raw_path),
                "-vf", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            logger.error("FFmpeg transcode to %s failed: %s", output_path.name, result.stderr[-500:])
            return False
    return True

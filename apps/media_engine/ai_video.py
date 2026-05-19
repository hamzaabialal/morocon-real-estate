"""AI video generation via Replicate.

When REPLICATE_API_TOKEN is set, this generates a cinematic AI video clip
from the property's cover image — real AI-rendered camera motion, not
just a Ken Burns slideshow.

Default model: kwaivgi/kling-v1.6-standard (Kuaishou's Kling 1.6).
  - Image-to-video with smooth cinematic camera moves
  - 5 or 10 second clips, 1080p
  - ~$0.05 per video (rates change; see https://replicate.com/pricing)

To use a different model, set REPLICATE_VIDEO_MODEL in .env, e.g.:
  REPLICATE_VIDEO_MODEL=minimax/video-01           # Hailuo, higher quality, ~$0.50
  REPLICATE_VIDEO_MODEL=stability-ai/stable-video-diffusion  # cheap fallback

Format: "owner/name" (uses latest version) or "owner/name:versionhash".

The function returns a tuple (reel_path, square_path) just like the FFmpeg
generator, so it's a drop-in replacement.
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
DEFAULT_MODEL = "kwaivgi/kling-v1.6-standard"


class ReplicateNotConfigured(Exception):
    """REPLICATE_API_TOKEN is not set — caller should fall back to FFmpeg."""


def generate_ai_video(property_obj):
    """Generate a cinematic AI video clip. Returns (reel_path, square_path) or None."""
    token = getattr(settings, "REPLICATE_API_TOKEN", "")
    if not token:
        raise ReplicateNotConfigured()

    image_url = resolve_image_url(property_obj)
    if not image_url:
        logger.warning("Property %s has no usable image; cannot run AI video.", property_obj.id)
        return None

    motion_prompt = build_motion_prompt(property_obj)
    prediction = create_prediction(token, image_url, motion_prompt, property_obj)
    if not prediction:
        return None

    output_url = poll_until_done(token, prediction["id"], timeout_seconds=600)
    if not output_url:
        return None

    temp_dir = Path(tempfile.mkdtemp(prefix=f"ai-video-{property_obj.id}-"))
    raw_path = temp_dir / "raw.mp4"
    if not download_video(output_url, raw_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    reel_path = temp_dir / "reel_ai.mp4"
    square_path = temp_dir / "square_ai.mp4"
    if not transcode_aspects(raw_path, reel_path, square_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    return str(reel_path), str(square_path)


def build_motion_prompt(property_obj):
    """Build a short camera-motion prompt that complements the still image."""
    category = property_obj.property_category or "property"
    motions = {
        "VILLA":   "slow cinematic dolly forward toward the villa entrance, gentle parallax",
        "RIAD":    "smooth pan across the courtyard, light pouring through the arches",
        "FLAT":    "slow push-in through the living space, soft natural light shifts",
        "HOUSE":   "elegant aerial reveal, slight zoom out, golden hour glow",
        "OFFICE":  "smooth slider tracking shot across the workspace",
        "TERRAIN": "drone cinematic pull-back revealing the landscape",
    }
    motion = motions.get(category, "slow cinematic camera move with subtle parallax")
    return f"{motion}, real estate showcase, photorealistic, no people"


def resolve_image_url(property_obj):
    """Pick the best image URL to feed the AI model (publicly reachable or data URL)."""
    main = property_obj.images.filter(is_main=True).first()
    if main and main.url and main.url.startswith("http"):
        return main.url
    first = property_obj.images.order_by("order").first()
    if first and first.url and first.url.startswith("http"):
        return first.url
    cover = property_obj.cover_image_url or ""
    if cover.startswith("http"):
        return cover
    if cover.startswith("/media/"):
        on_disk = Path(settings.BASE_DIR) / cover.lstrip("/")
        if on_disk.exists():
            return file_to_data_url(on_disk)
    if cover.startswith("/assets/"):
        asset_path = Path(settings.BASE_DIR) / "templates" / "assets" / cover[len("/assets/"):]
        if asset_path.exists():
            return file_to_data_url(asset_path)
    return None


def file_to_data_url(local_path):
    """Convert a local image to a base64 data URL (Replicate accepts these)."""
    import base64
    import mimetypes
    mime = mimetypes.guess_type(str(local_path))[0] or "image/jpeg"
    data = base64.b64encode(local_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def create_prediction(token, image_url, motion_prompt, property_obj):
    """Kick off a Replicate prediction. Picks the right input schema per model family."""
    model = getattr(settings, "REPLICATE_VIDEO_MODEL", "") or DEFAULT_MODEL
    model_name = model.split(":", 1)[0]

    if "kling" in model_name.lower():
        input_data = {
            "start_image": image_url,
            "prompt": motion_prompt,
            "duration": 5,
            "aspect_ratio": "9:16",
            "cfg_scale": 0.5,
        }
    elif "minimax" in model_name.lower() or "hailuo" in model_name.lower():
        input_data = {
            "first_frame_image": image_url,
            "prompt": motion_prompt,
            "prompt_optimizer": True,
        }
    else:
        input_data = {
            "input_image": image_url,
            "frames_per_second": 6,
            "motion_bucket_id": 127,
            "cond_aug": 0.02,
            "sizing_strategy": "maintain_aspect_ratio",
        }

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    try:
        if ":" in model:
            version = model.split(":", 1)[1]
            response = httpx.post(
                f"{REPLICATE_API}/predictions",
                headers=headers,
                json={"version": version, "input": input_data},
                timeout=60.0,
            )
        else:
            response = httpx.post(
                f"{REPLICATE_API}/models/{model_name}/predictions",
                headers=headers,
                json={"input": input_data},
                timeout=60.0,
            )
        if response.status_code >= 400:
            logger.error("Replicate create %s failed: %s", response.status_code, response.text[:500])
            return None
        return response.json()
    except httpx.HTTPError as exc:
        logger.exception("Replicate create_prediction error: %s", exc)
        return None


def poll_until_done(token, prediction_id, timeout_seconds=600):
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
        (reel_path, f"{common_filter},crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2"),
        (square_path, f"{common_filter},crop=1080:1080:(in_w-1080)/2:(in_h-1080)/2"),
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
            capture_output=True, text=True,
        )
        if result.returncode:
            logger.error("FFmpeg transcode to %s failed: %s", output_path.name, result.stderr[-500:])
            return False
    return True

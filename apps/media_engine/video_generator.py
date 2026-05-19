"""FFmpeg video generation for property listings."""
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from django.conf import settings


logger = logging.getLogger(__name__)


FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def resolve_font_file():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


class FFmpegNotInstalledError(RuntimeError):
    """Raised when FFmpeg is not available on PATH or via imageio-ffmpeg."""


def get_ffmpeg_binary():
    """Return the path to an FFmpeg binary, preferring system, falling back to bundled."""
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise FFmpegNotInstalledError(
            "FFmpeg is not on PATH and imageio-ffmpeg is not installed. "
            "Install it with: pip install imageio-ffmpeg"
        ) from exc


def generate_property_video(property_obj):
    """Generate the reel + square videos.

    Pipeline: AI video (Replicate) if configured → FFmpeg slideshow fallback →
    text overlay (price + location) → optional music mix-in.
    """
    raw_paths = None
    try:
        from apps.media_engine.ai_video import generate_ai_video, ReplicateNotConfigured
        raw_paths = generate_ai_video(property_obj)
    except ReplicateNotConfigured:
        pass
    except Exception:
        logger.exception("AI video generation failed; falling back to FFmpeg slideshow")

    if not raw_paths:
        raw_paths = generate_slideshow_video(property_obj)
    if not raw_paths:
        return None

    return finalize_videos(property_obj, raw_paths)


def finalize_videos(property_obj, raw_paths):
    """Apply text overlay + optional music to both reel and square."""
    reel_in, square_in = raw_paths
    out_dir = Path(reel_in).parent
    reel_out = out_dir / "reel_final.mp4"
    square_out = out_dir / "square_final.mp4"

    success_reel = apply_overlay_and_music(property_obj, reel_in, reel_out, vertical=True)
    success_sq = apply_overlay_and_music(property_obj, square_in, square_out, vertical=False)

    return (str(reel_out if success_reel else reel_in), str(square_out if success_sq else square_in))


def apply_overlay_and_music(property_obj, input_path, output_path, vertical):
    """Burn text overlay + optionally mix in background music."""
    ffmpeg = get_ffmpeg_binary()
    font = resolve_font_file()

    title = (property_obj.formatted_address or property_obj.yakeey_ref or "").strip()
    city = getattr(property_obj.city, "name", "") if property_obj.city_id else ""
    price_text = format_price_for_overlay(property_obj.price, property_obj.currency)
    badge = "AI Reel"

    filters = []
    if font:
        font_escaped = font.replace("\\", "/").replace(":", "\\:")
        text_size_price = 60 if vertical else 48
        text_size_meta = 32 if vertical else 28
        text_size_badge = 24 if vertical else 22
        if price_text:
            filters.append(
                f"drawtext=fontfile='{font_escaped}':text='{_escape(price_text)}':"
                f"fontcolor=white:fontsize={text_size_price}:borderw=3:bordercolor=black@0.7:"
                f"x=40:y=40"
            )
        meta_line = " · ".join([p for p in [city, title[:30]] if p])
        if meta_line:
            filters.append(
                f"drawtext=fontfile='{font_escaped}':text='{_escape(meta_line)}':"
                f"fontcolor=white:fontsize={text_size_meta}:borderw=2:bordercolor=black@0.7:"
                f"x=40:y=h-th-40"
            )
        filters.append(
            f"drawtext=fontfile='{font_escaped}':text='{_escape(badge)}':"
            f"fontcolor=white:fontsize={text_size_badge}:box=1:boxcolor=0xb48438@0.85:boxborderw=10:"
            f"x=w-tw-40:y=40"
        )

    music_path = getattr(settings, "BACKGROUND_MUSIC_PATH", "") or os.environ.get("BACKGROUND_MUSIC_PATH", "")
    if music_path and not Path(music_path).exists():
        logger.warning("BACKGROUND_MUSIC_PATH=%s does not exist; skipping music mix.", music_path)
        music_path = ""

    command = [ffmpeg, "-y", "-i", str(input_path)]
    if music_path:
        command += ["-stream_loop", "-1", "-i", str(music_path)]

    if filters:
        command += ["-vf", ",".join(filters)]

    if music_path:
        command += [
            "-filter_complex",
            "[1:a]volume=0.35,afade=t=in:st=0:d=1,afade=t=out:st=28:d=2[a1];" if False else "[1:a]volume=0.35[a1]",
            "-map", "0:v", "-map", "[a1]",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
        ]
    command += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        logger.warning("Overlay/music pass failed (%s): %s", output_path.name, result.stderr[-400:])
        return False
    return True


def format_price_for_overlay(price, currency):
    if not price:
        return ""
    try:
        n = float(price)
    except (TypeError, ValueError):
        return ""
    cur = currency or "MAD"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M {cur}".replace(".0M", "M")
    if n >= 1_000:
        return f"{int(n/1_000)}K {cur}"
    return f"{int(n)} {cur}"


def _escape(text):
    """Escape special chars for FFmpeg drawtext."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "’")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def generate_slideshow_video(property_obj):
    """Original Ken-Burns FFmpeg slideshow generator, used as a fallback."""
    ffmpeg_binary = get_ffmpeg_binary()
    image_urls = collect_image_urls(property_obj)
    if not image_urls:
        return None

    temp_dir = Path(tempfile.mkdtemp(prefix=f"property-media-{property_obj.id}-"))
    image_dir = temp_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    downloaded = download_images(image_urls, image_dir)
    if not downloaded:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    reel_path = temp_dir / "reel.mp4"
    square_path = temp_dir / "square.mp4"
    input_pattern = str(image_dir / "image_%03d.jpg")

    run_ffmpeg(
        ffmpeg_binary,
        input_pattern,
        reel_path,
        "zoompan=z=1.05:d=180,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
    )
    run_ffmpeg(
        ffmpeg_binary,
        input_pattern,
        square_path,
        "zoompan=z=1.05:d=180,scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,setsar=1",
    )
    return str(reel_path), str(square_path)


def collect_image_urls(property_obj):
    """Return up to 5 image URLs from PropertyImage rows, falling back to cover_image_url."""
    image_rows = list(property_obj.images.order_by("order")[:5])
    urls = [image.url for image in image_rows if image.url]
    if urls:
        return urls
    if property_obj.cover_image_url:
        return [property_obj.cover_image_url]
    return []


def download_images(image_urls, image_dir):
    """Materialize images into the working directory as image_NNN.jpg files."""
    downloaded = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for index, url in enumerate(image_urls):
            dest = image_dir / f"image_{index:03d}.jpg"
            local_source = resolve_local_asset(url)
            try:
                if local_source:
                    shutil.copyfile(local_source, dest)
                else:
                    response = client.get(url)
                    response.raise_for_status()
                    dest.write_bytes(response.content)
            except (httpx.HTTPError, OSError):
                continue
            downloaded.append(dest)
    return downloaded


def resolve_local_asset(url):
    """If url points at a bundled /assets/* file, return the on-disk Path; else None."""
    if not url or not isinstance(url, str):
        return None
    if url.startswith("/assets/"):
        asset_path = settings.BASE_DIR / "templates" / "assets" / url[len("/assets/"):]
        if asset_path.exists():
            return asset_path
    return None


def run_ffmpeg(ffmpeg_binary, input_pattern, output_path, video_filter):
    """Run the FFmpeg slideshow command for one output format."""
    command = [
        ffmpeg_binary,
        "-y",
        "-framerate",
        "1/6",
        "-i",
        input_pattern,
        "-vf",
        video_filter,
        "-c:v",
        "libx264",
        "-t",
        "30",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(
            f"FFmpeg failed with exit code {completed.returncode}: {completed.stderr}"
        )

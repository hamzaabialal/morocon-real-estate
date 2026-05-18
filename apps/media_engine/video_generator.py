"""FFmpeg video generation for property listings."""
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from django.conf import settings


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
    """Generate vertical and square property videos from property images."""
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

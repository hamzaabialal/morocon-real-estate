"""FFmpeg video generation for property listings."""
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx


class FFmpegNotInstalledError(RuntimeError):
    """Raised when FFmpeg is not available on PATH."""


def ensure_ffmpeg_available():
    """Ensure FFmpeg is installed and available on PATH."""
    if not shutil.which("ffmpeg"):
        raise FFmpegNotInstalledError(
            "FFmpeg is not installed or not on PATH. On Windows, download it from "
            "https://ffmpeg.org/download.html and add the bin directory to PATH."
        )


def generate_property_video(property_obj):
    """Generate vertical and square property videos from the first five images."""
    ensure_ffmpeg_available()
    images = list(property_obj.images.order_by("order")[:5])
    if not images:
        return None

    temp_dir = Path(tempfile.mkdtemp(prefix=f"property-media-{property_obj.id}-"))
    image_dir = temp_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    downloaded_images = download_images(images, image_dir)
    if not downloaded_images:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    reel_path = temp_dir / "reel.mp4"
    square_path = temp_dir / "square.mp4"
    input_pattern = str(image_dir / "image_%03d.jpg")

    run_ffmpeg(
        input_pattern,
        reel_path,
        "zoompan=z=1.05:d=180,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
    )
    run_ffmpeg(
        input_pattern,
        square_path,
        "zoompan=z=1.05:d=180,scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,setsar=1",
    )
    return str(reel_path), str(square_path)


def download_images(images, image_dir):
    """Download images to a sequential file pattern for FFmpeg."""
    downloaded = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for index, image in enumerate(images):
            try:
                response = client.get(image.url)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            path = image_dir / f"image_{index:03d}.jpg"
            path.write_bytes(response.content)
            downloaded.append(path)
    return downloaded


def run_ffmpeg(input_pattern, output_path, video_filter):
    """Run the FFmpeg slideshow command for one output format."""
    command = [
        "ffmpeg",
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

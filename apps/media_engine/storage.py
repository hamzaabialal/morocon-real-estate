"""Media storage helpers — Cloudflare R2/S3 when configured, local MEDIA_ROOT otherwise."""
import shutil
from pathlib import Path

from django.conf import settings


def upload_media_to_s3(local_path, property_id, filename):
    """Persist generated media and return a publicly addressable URL.

    Uses S3/R2 when AWS credentials are configured; otherwise copies the file
    to MEDIA_ROOT and returns the MEDIA_URL path so dev can verify videos
    without S3 keys.
    """
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        from storages.backends.s3boto3 import S3Boto3Storage

        storage = S3Boto3Storage()
        key = f"media/videos/{property_id}/{filename}"
        with Path(local_path).open("rb") as file_obj:
            saved_key = storage.save(key, file_obj)
        return storage.url(saved_key)

    media_root = Path(settings.MEDIA_ROOT)
    dest_dir = media_root / "videos" / str(property_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    shutil.copyfile(local_path, dest_path)
    media_url = settings.MEDIA_URL.rstrip("/")
    return f"{media_url}/videos/{property_id}/{filename}"

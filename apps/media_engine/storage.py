"""Cloudflare R2/S3 storage helpers for generated media."""
from pathlib import Path


def upload_media_to_s3(local_path, property_id, filename):
    """Upload local media to R2/S3 and return the public URL."""
    from storages.backends.s3boto3 import S3Boto3Storage

    storage = S3Boto3Storage()
    key = f"media/videos/{property_id}/{filename}"
    with Path(local_path).open("rb") as file_obj:
        saved_key = storage.save(key, file_obj)
    return storage.url(saved_key)

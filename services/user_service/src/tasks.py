from __future__ import annotations

import io
import logging

from src.celery_app import celery
from src.config import settings

logger = logging.getLogger(__name__)

THUMB_SIZE = (320, 320)
_thumb_bucket_ready = False


@celery.task(name="src.tasks.generate_thumbnail", bind=True, max_retries=3)
def generate_thumbnail(self, s3_key: str, photo_id: str) -> None:
    global _thumb_bucket_ready
    try:
        from minio import Minio
        from PIL import Image

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )

        if not _thumb_bucket_ready:
            if not client.bucket_exists(settings.minio_thumb_bucket):
                client.make_bucket(settings.minio_thumb_bucket)
            _thumb_bucket_ready = True

        response = client.get_object(settings.minio_bucket, s3_key)
        try:
            original = Image.open(io.BytesIO(response.read()))
        finally:
            response.close()
            response.release_conn()

        original.thumbnail(THUMB_SIZE, Image.LANCZOS)
        buf = io.BytesIO()
        original.convert("RGB").save(buf, format="JPEG", quality=85)
        buf.seek(0)

        thumb_key = f"thumbs/{s3_key.split('/', 1)[-1]}"
        client.put_object(
            settings.minio_thumb_bucket,
            thumb_key,
            buf,
            length=buf.getbuffer().nbytes,
            content_type="image/jpeg",
        )
        logger.info("Thumbnail generated: photo_id=%s key=%s", photo_id, thumb_key)
    except Exception as exc:
        logger.exception("generate_thumbnail failed: photo_id=%s", photo_id)
        raise self.retry(exc=exc, countdown=30)

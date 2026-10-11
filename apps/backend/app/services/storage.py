import asyncio
import hashlib
import io
import uuid
import warnings
from functools import lru_cache
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings, get_settings

ALLOWED_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


class StorageNotConfigured(RuntimeError):
    """Object storage is not configured for media persistence."""


class InvalidImage(ValueError):
    """An uploaded image does not pass the media safety checks."""


@lru_cache(maxsize=8)
def _s3_client(endpoint: str, region: str, access_key: str, secret_key: str, addressing_style: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": addressing_style}),
    )


def _secret_value(*values) -> str | None:
    for value in values:
        if value and value.get_secret_value().strip():
            return value.get_secret_value()
    return None


def _storage_config(settings: Settings) -> tuple[object, str, str]:
    endpoint = settings.aws_endpoint_url_s3 or settings.object_storage_endpoint
    access_key = _secret_value(settings.aws_access_key_id, settings.object_storage_access_key_id)
    secret_key = _secret_value(
        settings.aws_secret_access_key, settings.object_storage_secret_access_key
    )
    region = settings.aws_region or settings.object_storage_region
    if not all((endpoint, settings.object_storage_bucket, access_key, secret_key)):
        raise StorageNotConfigured("S3-compatible object storage is not configured")

    client = _s3_client(
        endpoint or "",
        region,
        access_key or "",
        secret_key or "",
        settings.object_storage_addressing_style,
    )
    return (client, settings.object_storage_bucket, settings.object_storage_public_base_url or "")


async def store_bytes(key: str, body: bytes, content_type: str) -> str:
    settings = get_settings()
    client, bucket, _ = _storage_config(settings)

    def put_object() -> None:
        client.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)

    try:
        await asyncio.to_thread(put_object)
    except (BotoCoreError, ClientError) as exc:
        raise StorageNotConfigured("Object storage upload failed") from exc
    return key


async def delete_object(key: str) -> None:
    settings = get_settings()
    client, bucket, _ = _storage_config(settings)

    def remove_object() -> None:
        client.delete_object(Bucket=bucket, Key=key)

    try:
        await asyncio.to_thread(remove_object)
    except (BotoCoreError, ClientError) as exc:
        raise StorageNotConfigured("Object storage delete failed") from exc


async def resolve_object_url(key: str) -> str:
    settings = get_settings()
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise StorageNotConfigured("Invalid object key")
    client, bucket, public_base = _storage_config(settings)
    if public_base:
        return f"{public_base.rstrip('/')}/{quote(key, safe='/')}"

    def create_url() -> str:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=settings.object_storage_url_ttl_seconds,
        )

    try:
        return await asyncio.to_thread(create_url)
    except (BotoCoreError, ClientError) as exc:
        raise StorageNotConfigured("Could not create object download URL") from exc


def is_owned_upload_key(key: str | None, owner_id: str) -> bool:
    owner_prefix = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:16]
    return bool(key and key.startswith(f"uploads/{owner_prefix}/") and ".." not in key.split("/"))


def sanitize_image(data: bytes, max_bytes: int) -> tuple[bytes, str, str]:
    if not data or len(data) > max_bytes:
        raise InvalidImage("Image is empty or exceeds the upload size limit")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(io.BytesIO(data))
            image_format = source.format
            source.verify()
            source = Image.open(io.BytesIO(data))
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise InvalidImage("Only JPEG, PNG, and WebP images are allowed")
            if source.width * source.height > 40_000_000:
                raise InvalidImage("Image dimensions are too large")

            extension, content_type = ALLOWED_IMAGE_FORMATS[image_format]
            source = ImageOps.exif_transpose(source)
            if image_format == "JPEG":
                output_image = source.convert("RGB")
            else:
                output_image = source.copy()
            output_image.info.clear()
            output = io.BytesIO()
            options = {"optimize": True}
            if image_format == "JPEG":
                options["quality"] = 90
            output_image.save(output, format=image_format, **options)
            sanitized = output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidImage("Uploaded file is not a safe, readable image") from exc

    if len(sanitized) > max_bytes:
        raise InvalidImage("Processed image exceeds the upload size limit")
    return sanitized, extension, content_type


async def store_uploaded_image(data: bytes, owner_id: str) -> str:
    settings = get_settings()
    sanitized, extension, content_type = sanitize_image(data, settings.upload_max_bytes)
    owner_prefix = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:16]
    key = f"uploads/{owner_prefix}/{uuid.uuid4()}{extension}"
    return await store_bytes(key, sanitized, content_type)

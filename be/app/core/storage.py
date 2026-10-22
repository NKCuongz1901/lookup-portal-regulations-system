"""Cloudflare R2 storage client (S3-compatible) via boto3."""
from functools import lru_cache
import unicodedata
from urllib.parse import quote
from uuid import uuid4

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache
def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def build_storage_key(document_id: int, original_name: str) -> str:
    safe_name = original_name.replace("/", "_").replace("\\", "_")
    return f"documents/{document_id}/{uuid4().hex}_{safe_name}"


def upload_bytes(*, storage_key: str, content: bytes, content_type: str) -> str:
    """Upload bytes to R2. Returns the storage_key."""
    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=storage_key,
        Body=content,
        ContentType=content_type,
    )
    return storage_key


def delete_object(storage_key: str) -> None:
    """Delete object from R2."""
    client = get_r2_client()
    client.delete_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=storage_key,
    )


def download_content_disposition(original_name: str) -> str:
    """Use an ASCII fallback and RFC 5987 UTF-8 filename, without header controls."""
    name = original_name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if unicodedata.category(char) not in {"Cc", "Cf"})
    name = name.strip()
    if name in {"", ".", ".."}:
        name = "download"
    fallback = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    fallback = fallback.replace('"', "_").strip() or "download"
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(name, safe="")}'


def generate_download_url(
    *, storage_key: str, original_name: str, mime_type: str, expires_in: int,
) -> str:
    """Check the object, then sign a GET that downloads under its original name.

    Signing alone does not contact R2. Let the caller distinguish missing objects
    from permission, credential, and connection errors raised by the SDK.
    """
    client = get_r2_client()
    client.head_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key)
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": storage_key,
            "ResponseContentDisposition": download_content_disposition(original_name),
            "ResponseContentType": mime_type,
            "ResponseCacheControl": "private, no-store",
        },
        ExpiresIn=expires_in,
        HttpMethod="GET",
    )

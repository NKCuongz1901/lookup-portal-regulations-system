"""Cloudflare R2 storage client (S3-compatible) via boto3."""
from functools import lru_cache
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

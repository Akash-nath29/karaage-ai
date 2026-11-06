"""Private S3-compatible object storage. Originals never go into Postgres (PRD rule 10)."""

from functools import cache
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings


@cache
def _client():  # type: ignore[no-untyped-def]  # boto3 clients are dynamically typed
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        # Path-style (endpoint/bucket/key): Supabase Storage needs it, and MinIO, R2 and S3 all accept it (D37).
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


@cache
def _ensure_bucket(bucket: str) -> None:
    try:
        _client().head_bucket(Bucket=bucket)
    except ClientError:
        _client().create_bucket(Bucket=bucket)


def put(key: str, data: bytes, content_type: str) -> None:
    _ensure_bucket(settings.s3_bucket)
    _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


def get(key: str) -> bytes:
    return _client().get_object(Bucket=settings.s3_bucket, Key=key)["Body"].read()


def delete(key: str) -> None:
    _client().delete_object(Bucket=settings.s3_bucket, Key=key)


def presigned_url(key: str, filename: str, expires_seconds: int = 300) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            # inline so PDFs open in the browser viewer (citation links use #page=N)
            "ResponseContentDisposition": f"inline; filename*=UTF-8''{quote(filename)}",
        },
        ExpiresIn=expires_seconds,
    )

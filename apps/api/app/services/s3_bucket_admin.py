"""Operações idempotentes de administração de buckets S3/MinIO."""

from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


def _client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code") or "")


def _status_code(exc: ClientError) -> int:
    return int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") or 0)


def is_missing_bucket(exc: ClientError) -> bool:
    return _status_code(exc) == 404 or _error_code(exc) in {
        "404",
        "NoSuchBucket",
        "NoSuchKey",
        "NotFound",
    }


def ensure_bucket(bucket: str) -> dict[str, Any]:
    client = _client()
    try:
        client.head_bucket(Bucket=bucket)
        return {"bucket": bucket, "created": False, "existing": True}
    except ClientError as exc:
        if not is_missing_bucket(exc):
            # 403 é falta de permissão/credencial; não significa bucket ausente.
            raise

    try:
        client.create_bucket(Bucket=bucket)
        return {"bucket": bucket, "created": True, "existing": False}
    except ClientError as exc:
        if _error_code(exc) == "BucketAlreadyOwnedByYou":
            return {"bucket": bucket, "created": False, "existing": True}
        raise


def _delete_batch(client: Any, bucket: str, objects: list[dict[str, str]]) -> None:
    for offset in range(0, len(objects), 1000):
        batch = objects[offset : offset + 1000]
        if batch:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": batch, "Quiet": True},
            )


def empty_and_delete_bucket(bucket: str) -> dict[str, Any]:
    client = _client()
    deleted_objects = 0
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if is_missing_bucket(exc):
            return {"bucket": bucket, "deleted": True, "already_missing": True, "objects": 0}
        raise

    try:
        paginator = client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket):
            objects = [
                {"Key": str(item["Key"]), "VersionId": str(item["VersionId"])}
                for item in [*(page.get("Versions") or []), *(page.get("DeleteMarkers") or [])]
                if item.get("Key") is not None and item.get("VersionId") is not None
            ]
            _delete_batch(client, bucket, objects)
            deleted_objects += len(objects)
    except ClientError as exc:
        if is_missing_bucket(exc):
            return {
                "bucket": bucket,
                "deleted": True,
                "already_missing": True,
                "objects": deleted_objects,
            }
        if _error_code(exc) not in {"NotImplemented", "InvalidRequest", "MethodNotAllowed"}:
            raise
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            objects = [
                {"Key": str(item["Key"])}
                for item in page.get("Contents") or []
                if item.get("Key") is not None
            ]
            _delete_batch(client, bucket, objects)
            deleted_objects += len(objects)

    try:
        client.delete_bucket(Bucket=bucket)
    except ClientError as exc:
        if not is_missing_bucket(exc):
            raise
    return {"bucket": bucket, "deleted": True, "already_missing": False, "objects": deleted_objects}

import asyncio
import re
from typing import Any, BinaryIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.errors import APIError
from app.core.tenant_context import TenantContext

SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\- ]{0,500}$")


class TenantFileService:
    def __init__(self, context: TenantContext) -> None:
        self.context = context
        self.bucket = context.storage_bucket
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    @staticmethod
    def normalize_key(key: str) -> str:
        clean = key.strip().replace("\\", "/").lstrip("/")
        while "//" in clean:
            clean = clean.replace("//", "/")
        if not clean or ".." in clean.split("/") or not SAFE_KEY_RE.fullmatch(clean):
            raise APIError("FILE_KEY_INVALID", "Chave de arquivo inválida.", 422)
        return clean

    def object_key(self, key: str) -> str:
        return f"files/{self.normalize_key(key)}"

    async def upload(self, key: str, fileobj: BinaryIO, content_type: str | None = None) -> dict[str, Any]:
        object_key = self.object_key(key)
        extra = {"ContentType": content_type} if content_type else None
        try:
            if extra:
                await asyncio.to_thread(self.s3.upload_fileobj, fileobj, self.bucket, object_key, ExtraArgs=extra)
            else:
                await asyncio.to_thread(self.s3.upload_fileobj, fileobj, self.bucket, object_key)
            head = await asyncio.to_thread(self.s3.head_object, Bucket=self.bucket, Key=object_key)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError("FILE_STORAGE_ERROR", "Falha ao armazenar arquivo no storage do tenant.", 424, {"error": str(exc)}) from exc
        return {
            "key": self.normalize_key(key),
            "object_key": object_key,
            "bucket": self.bucket,
            "size_bytes": int(head.get("ContentLength", 0)),
            "content_type": head.get("ContentType"),
            "etag": str(head.get("ETag", "")).strip('"'),
        }

    async def get_object(self, key: str) -> dict[str, Any]:
        object_key = self.object_key(key)
        try:
            return await asyncio.to_thread(self.s3.get_object, Bucket=self.bucket, Key=object_key)
        except ClientError as exc:
            status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if status == 404 or exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchObject"}:
                raise APIError("FILE_NOT_FOUND", "Arquivo não encontrado.", 404) from exc
            raise APIError("FILE_STORAGE_ERROR", "Falha ao obter arquivo do storage do tenant.", 424, {"error": str(exc)}) from exc

    async def delete(self, key: str) -> dict[str, Any]:
        object_key = self.object_key(key)
        try:
            await asyncio.to_thread(self.s3.delete_object, Bucket=self.bucket, Key=object_key)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError("FILE_STORAGE_ERROR", "Falha ao excluir arquivo do storage do tenant.", 424, {"error": str(exc)}) from exc
        return {"deleted": True, "key": self.normalize_key(key), "bucket": self.bucket}

    async def list(self, prefix: str = "", limit: int = 200) -> list[dict[str, Any]]:
        clean_prefix = self.normalize_key(prefix) if prefix.strip() else ""
        object_prefix = f"files/{clean_prefix}" if clean_prefix else "files/"
        try:
            result = await asyncio.to_thread(
                self.s3.list_objects_v2,
                Bucket=self.bucket,
                Prefix=object_prefix,
                MaxKeys=min(max(limit, 1), 1000),
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError("FILE_STORAGE_ERROR", "Falha ao listar arquivos do tenant.", 424, {"error": str(exc)}) from exc
        rows: list[dict[str, Any]] = []
        for item in result.get("Contents", []):
            object_key = str(item.get("Key", ""))
            rows.append(
                {
                    "key": object_key.removeprefix("files/"),
                    "size_bytes": int(item.get("Size", 0)),
                    "etag": str(item.get("ETag", "")).strip('"'),
                    "last_modified": item.get("LastModified"),
                }
            )
        return rows

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

    @staticmethod
    def ensure_within_quota(
        *,
        used_bytes: int,
        existing_bytes: int,
        incoming_bytes: int,
        quota_bytes: int,
    ) -> int:
        projected = max(0, used_bytes - existing_bytes) + max(0, incoming_bytes)
        if projected > quota_bytes:
            raise APIError(
                "STORAGE_QUOTA_EXCEEDED",
                "A cota de armazenamento desta empresa foi atingida.",
                413,
                {
                    "quota_bytes": quota_bytes,
                    "used_bytes": used_bytes,
                    "incoming_bytes": incoming_bytes,
                    "projected_bytes": projected,
                },
            )
        return projected

    @staticmethod
    def _file_size(fileobj: BinaryIO) -> int:
        try:
            current = fileobj.tell()
            fileobj.seek(0, 2)
            size = int(fileobj.tell())
            fileobj.seek(current)
            return size
        except (AttributeError, OSError, ValueError) as exc:
            raise APIError(
                "FILE_SIZE_UNAVAILABLE",
                "Não foi possível determinar o tamanho do arquivo antes do envio.",
                422,
            ) from exc

    async def _existing_size(self, object_key: str) -> int:
        try:
            head = await asyncio.to_thread(
                self.s3.head_object,
                Bucket=self.bucket,
                Key=object_key,
            )
            return int(head.get("ContentLength", 0))
        except ClientError as exc:
            status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if status == 404 or code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                return 0
            raise APIError(
                "FILE_STORAGE_ERROR",
                "Falha ao consultar o arquivo no storage do tenant.",
                424,
                {"error": str(exc)},
            ) from exc

    async def usage_bytes(self) -> int:
        total = 0
        continuation: str | None = None
        try:
            while True:
                kwargs: dict[str, Any] = {
                    "Bucket": self.bucket,
                    "Prefix": "files/",
                    "MaxKeys": 1000,
                }
                if continuation:
                    kwargs["ContinuationToken"] = continuation
                result = await asyncio.to_thread(self.s3.list_objects_v2, **kwargs)
                total += sum(int(item.get("Size", 0)) for item in result.get("Contents", []))
                if not result.get("IsTruncated"):
                    break
                continuation = str(result.get("NextContinuationToken") or "") or None
                if continuation is None:
                    break
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError(
                "FILE_STORAGE_ERROR",
                "Falha ao calcular o uso do storage do tenant.",
                424,
                {"error": str(exc)},
            ) from exc
        return total

    async def quota_status(self) -> dict[str, Any]:
        used = await self.usage_bytes()
        quota = max(1, int(self.context.storage_quota_bytes))
        remaining = max(0, quota - used)
        return {
            "bucket": self.bucket,
            "quota_bytes": quota,
            "used_bytes": used,
            "remaining_bytes": remaining,
            "usage_percent": round(min(100.0, (used / quota) * 100), 2),
        }

    async def upload(
        self,
        key: str,
        fileobj: BinaryIO,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        normalized = self.normalize_key(key)
        object_key = f"files/{normalized}"
        incoming_size = self._file_size(fileobj)
        used_before = await self.usage_bytes()
        existing_size = await self._existing_size(object_key)
        projected = self.ensure_within_quota(
            used_bytes=used_before,
            existing_bytes=existing_size,
            incoming_bytes=incoming_size,
            quota_bytes=self.context.storage_quota_bytes,
        )
        try:
            fileobj.seek(0)
        except (AttributeError, OSError, ValueError):
            pass
        extra = {"ContentType": content_type} if content_type else None
        try:
            if extra:
                await asyncio.to_thread(
                    self.s3.upload_fileobj,
                    fileobj,
                    self.bucket,
                    object_key,
                    ExtraArgs=extra,
                )
            else:
                await asyncio.to_thread(
                    self.s3.upload_fileobj,
                    fileobj,
                    self.bucket,
                    object_key,
                )
            head = await asyncio.to_thread(
                self.s3.head_object,
                Bucket=self.bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError(
                "FILE_STORAGE_ERROR",
                "Falha ao armazenar arquivo no storage do tenant.",
                424,
                {"error": str(exc)},
            ) from exc
        actual_size = int(head.get("ContentLength", incoming_size))
        projected = max(0, used_before - existing_size) + actual_size
        quota = self.context.storage_quota_bytes
        return {
            "key": normalized,
            "object_key": object_key,
            "bucket": self.bucket,
            "size_bytes": actual_size,
            "content_type": head.get("ContentType"),
            "etag": str(head.get("ETag", "")).strip('"'),
            "storage": {
                "quota_bytes": quota,
                "used_bytes": projected,
                "remaining_bytes": max(0, quota - projected),
                "usage_percent": round(min(100.0, (projected / max(1, quota)) * 100), 2),
            },
        }

    async def get_object(self, key: str) -> dict[str, Any]:
        object_key = self.object_key(key)
        try:
            return await asyncio.to_thread(
                self.s3.get_object,
                Bucket=self.bucket,
                Key=object_key,
            )
        except ClientError as exc:
            status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if status == 404 or exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchObject"}:
                raise APIError("FILE_NOT_FOUND", "Arquivo não encontrado.", 404) from exc
            raise APIError(
                "FILE_STORAGE_ERROR",
                "Falha ao obter arquivo do storage do tenant.",
                424,
                {"error": str(exc)},
            ) from exc

    async def delete(self, key: str) -> dict[str, Any]:
        object_key = self.object_key(key)
        try:
            await asyncio.to_thread(
                self.s3.delete_object,
                Bucket=self.bucket,
                Key=object_key,
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError(
                "FILE_STORAGE_ERROR",
                "Falha ao excluir arquivo do storage do tenant.",
                424,
                {"error": str(exc)},
            ) from exc
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
            raise APIError(
                "FILE_STORAGE_ERROR",
                "Falha ao listar arquivos do tenant.",
                424,
                {"error": str(exc)},
            ) from exc
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

from collections.abc import Iterator
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.api.deps import get_tenant_context
from app.core.responses import success
from app.core.errors import APIError
from app.core.tenant_context import TenantContext
from app.services.file_service import TenantFileService

router = APIRouter()


class FileAccessRequest(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    operation: Literal["download", "upload"] = "download"


def _ordinary_key(key: str) -> str:
    normalized = TenantFileService.normalize_key(key)
    if normalized == "profiles-private" or normalized.startswith("profiles-private/"):
        raise APIError("FILE_PRIVATE_PROFILE", "Fotos de perfil são acessadas somente pelo perfil do titular.", 403)
    return normalized


def _stream(body: Any) -> Iterator[bytes]:
    try:
        yield from body.iter_chunks(chunk_size=64 * 1024)
    finally:
        body.close()


def _public_url(key: str) -> str | None:
    normalized = TenantFileService.normalize_key(key)
    if normalized.startswith("landing/"):
        return f"/api/v1/public/assets/{quote(normalized, safe='/')}"
    return None


@router.get("/quota")
async def storage_quota(
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await TenantFileService(context).quota_status())


@router.post("/signed-url")
async def signed_url(
    payload: FileAccessRequest,
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    service = TenantFileService(context)
    key = _ordinary_key(payload.key)
    if payload.operation == "upload":
        return success(
            {
                "mode": "api-proxy",
                "method": "POST",
                "url": "/api/v1/files/upload",
                "fields": {"key": key},
                "bucket": context.storage_bucket,
                "quota": await service.quota_status(),
            }
        )
    return success(
        {
            "mode": "api-proxy",
            "method": "GET",
            "url": f"/api/v1/files/content/{quote(key, safe='/')}",
            "public_url": _public_url(key),
            "bucket": context.storage_bucket,
        }
    )


@router.post("/upload")
async def upload_file(
    key: str = Form(...),
    file: UploadFile = File(...),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    try:
        result = await TenantFileService(context).upload(_ordinary_key(key), file.file, file.content_type)
        result["public_url"] = _public_url(result["key"])
        return success(result)
    finally:
        await file.close()


@router.get("")
async def list_files(
    prefix: str = Query(default="", max_length=500),
    limit: int = Query(default=200, ge=1, le=1000),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    # Compatibilidade: mantém `data` como lista, exatamente como antes desta PR.
    # A cota fica no endpoint separado `/files/quota`.
    if prefix.strip():
        _ordinary_key(prefix)
    rows = await TenantFileService(context).list(prefix=prefix, limit=limit)
    return success([row for row in rows if not str(row["key"]).startswith("profiles-private/")])


@router.get("/content/{key:path}")
async def download_file(
    key: str,
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    result = await TenantFileService(context).get_object(_ordinary_key(key))
    headers = {
        "Content-Disposition": f'inline; filename="{TenantFileService.normalize_key(key).split("/")[-1]}"',
        "ETag": str(result.get("ETag", "")),
    }
    return StreamingResponse(
        _stream(result["Body"]),
        media_type=str(result.get("ContentType") or "application/octet-stream"),
        headers=headers,
    )


@router.delete("/{key:path}")
async def delete_file(
    key: str,
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    service = TenantFileService(context)
    result = await service.delete(_ordinary_key(key))
    result["storage"] = await service.quota_status()
    return success(result)

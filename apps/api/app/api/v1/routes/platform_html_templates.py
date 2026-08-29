import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_platform_permission
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.html_template_contract import HtmlTemplateContract
from app.services.html_template_import_service import HtmlTemplateImportService
from app.services.html_template_package_service import (
    MAX_ARCHIVE_BYTES,
    HtmlTemplatePackageService,
)

router = APIRouter()


class HtmlTemplateValidate(BaseModel):
    landing_html: str | None = None
    booking_html: str | None = None


class HtmlTemplateImport(BaseModel):
    landing_html: str | None = None
    booking_html: str | None = None
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    scope: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] = "INTERNAL"
    default_for_new_tenants: bool = False
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] = Field(default_factory=list)
    publish: bool = False
    update_existing: bool = True


def _selected_tenants(raw: str) -> list[str]:
    if not raw.strip():
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APIError(
            "TEMPLATE_SELECTED_TENANTS_INVALID",
            "A seleção de clientes está inválida.",
            422,
        ) from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise APIError(
            "TEMPLATE_SELECTED_TENANTS_INVALID",
            "A seleção de clientes deve ser uma lista.",
            422,
        )
    return [item.strip() for item in value if item.strip()]


async def _archive(upload: UploadFile) -> bytes:
    if upload.filename and not upload.filename.lower().endswith(".zip"):
        raise APIError(
            "HTML_TEMPLATE_PACKAGE_EXTENSION_INVALID",
            "Selecione um pacote .zip do Scheduler Pro.",
            422,
        )
    data = await upload.read(MAX_ARCHIVE_BYTES + 1)
    if len(data) > MAX_ARCHIVE_BYTES:
        raise APIError(
            "HTML_TEMPLATE_PACKAGE_TOO_LARGE",
            "O pacote ZIP excede 50 MB.",
            413,
        )
    return data


@router.get("/contract")
async def html_template_contract(
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(HtmlTemplateContract.descriptor())


@router.post("/validate-package")
async def validate_html_template_package(
    package: UploadFile = File(...),
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(HtmlTemplatePackageService.validate(await _archive(package)))


@router.post("/import-package")
async def import_html_template_package(
    package: UploadFile = File(...),
    scope: str = Form(""),
    publish: bool = Form(False),
    update_existing: bool = Form(True),
    exclusive_tenant_id: str = Form(""),
    selected_tenant_ids: str = Form("[]"),
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    parsed = HtmlTemplatePackageService.ensure(await _archive(package))
    metadata = parsed["package"]
    documents = parsed["documents"]
    selected = _selected_tenants(selected_tenant_ids)
    result = await HtmlTemplateImportService(session).import_pair(
        landing_html=documents.get("LANDING"),
        booking_html=documents.get("BOOKING"),
        name=str(metadata["name"]),
        description=metadata.get("description"),
        segment=metadata.get("segment"),
        actor=principal.email,
        scope=scope.strip().upper() or str(metadata.get("scope") or "INTERNAL"),
        exclusive_tenant_id=exclusive_tenant_id.strip() or None,
        selected_tenant_ids=selected,
        default_for_new_tenants=bool(metadata.get("default_for_new_tenants", False)),
        publish=publish,
        update_existing=update_existing,
        template_key=str(metadata.get('key') or ''),
        experience_metadata=parsed.get('experience'),
    )
    return success(
        {
            **result,
            "package": {
                **metadata,
                "surfaces": parsed["surfaces"],
                "archive_bytes": parsed["archive_bytes"],
                "file_count": parsed["file_count"],
            },
        }
    )


# Compatibilidade para integrações administrativas anteriores. A interface
# oficial usa o pacote ZIP; estes endpoints continuam disponíveis para não
# quebrar automações existentes que já enviavam os dois HTMLs diretamente.
@router.post("/validate")
async def validate_html_template_pair(
    payload: HtmlTemplateValidate,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(
        HtmlTemplateContract.validate_pair(
            landing_html=payload.landing_html,
            booking_html=payload.booking_html,
        )
    )


@router.post("/import")
async def import_html_template_pair(
    payload: HtmlTemplateImport,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await HtmlTemplateImportService(session).import_pair(
            landing_html=payload.landing_html,
            booking_html=payload.booking_html,
            name=payload.name,
            description=payload.description,
            segment=payload.segment,
            actor=principal.email,
            scope=payload.scope,
            exclusive_tenant_id=payload.exclusive_tenant_id,
            selected_tenant_ids=payload.selected_tenant_ids,
            default_for_new_tenants=payload.default_for_new_tenants,
            publish=payload.publish,
            update_existing=payload.update_existing,
        )
    )

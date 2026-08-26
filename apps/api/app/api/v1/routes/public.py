from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

import bleach
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import (
    get_platform_session,
    get_tenant_context,
    get_tenant_session,
    require_tenant_capability,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.agenda_report_delivery_service import verify_report_token
from app.services.branding_service import BrandingService
from app.services.file_service import TenantFileService
from app.services.landing_service import LandingPageService
from app.services.public_booking_service import PublicBookingService
from app.services.template_contract import TemplateContract

router = APIRouter()
PUBLIC_LANDING_ASSET_PREFIX = "landing/"
PUBLIC_LANDING_ASSET_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/avif",
    "image/svg+xml",
}


class PublicBookingCreate(BaseModel):
    service_id: str | None = Field(default=None, min_length=10, max_length=80)
    professional_id: str | None = Field(default=None, min_length=10, max_length=80)
    starts_at: datetime
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=80)
    customer_email: EmailStr | None = None


def _public_base_url(context: TenantContext) -> str:
    scheme = "http" if context.hostname in {"localhost", "127.0.0.1"} else "https"
    return f"{scheme}://{context.hostname}"


def _safe_booking_html(value: str) -> str:
    return bleach.clean(
        value,
        tags={
            "section", "div", "p", "span", "h1", "h2", "h3", "h4",
            "strong", "em", "small", "br", "ul", "ol", "li", "a",
        },
        attributes={"a": ["href", "target", "rel"], "*": ["class"]},
        protocols={"http", "https", "mailto", "tel"},
        strip=True,
    )


def _apply_booking_template_copy(config: dict[str, Any]) -> None:
    template = config.get("booking_template")
    if not isinstance(template, dict):
        return
    content = template.get("content")
    if not isinstance(content, dict):
        return
    TemplateContract.ensure_content("BOOKING", content, strict=False)
    copy = content.get("copy")
    if not isinstance(copy, dict):
        return
    title = str(copy.get("title") or "").strip()
    subtitle = str(copy.get("subtitle") or "").strip()
    success_message = str(copy.get("success") or "").strip()
    if title:
        config["title"] = title
    if subtitle:
        config["subtitle"] = subtitle
    if success_message:
        config["success_message"] = success_message


def _stream(body: Any) -> Iterator[bytes]:
    try:
        yield from body.iter_chunks(chunk_size=64 * 1024)
    finally:
        body.close()


@router.get("/assets/{key:path}")
async def public_landing_asset(
    key: str,
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    normalized = TenantFileService.normalize_key(key)
    if not normalized.startswith(PUBLIC_LANDING_ASSET_PREFIX):
        raise APIError("PUBLIC_ASSET_NOT_FOUND", "Arquivo público não encontrado.", 404)

    result = await TenantFileService(context).get_object(normalized)
    content_type = str(result.get("ContentType") or "application/octet-stream").lower()
    if content_type not in PUBLIC_LANDING_ASSET_TYPES:
        try:
            result["Body"].close()
        finally:
            raise APIError("PUBLIC_ASSET_NOT_FOUND", "Arquivo público não encontrado.", 404)

    return StreamingResponse(
        _stream(result["Body"]),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=300, must-revalidate",
            "ETag": str(result.get("ETag", "")),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/agenda-report/{token}")
async def public_agenda_report(
    token: str,
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    payload = verify_report_token(token, context.tenant_id)
    key = TenantFileService.normalize_key(str(payload.get("key") or ""))
    if not key.startswith("reports/agenda/"):
        raise APIError("AGENDA_REPORT_LINK_INVALID", "Link de relatório inválido.", 404)
    result = await TenantFileService(context).get_object(key)
    content_type = str(
        payload.get("type") or result.get("ContentType") or "application/octet-stream"
    )
    filename = key.rsplit("/", 1)[-1]
    return StreamingResponse(
        _stream(result["Body"]),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store, max-age=0",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/landing")
async def landing(
    _: None = Depends(require_tenant_capability("landing_pages")),
    slug: str = "home",
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    branding = await BrandingService(platform_session).manifest_for_context(context)
    page = await LandingPageService(tenant_session).get_published(slug)
    return success({
        "tenant": {"id": context.tenant_id, "slug": context.slug},
        "branding": branding,
        "landing_page": page,
    })


@router.get("/booking")
async def public_booking_catalog(
    _: None = Depends(require_tenant_capability("public_booking")),
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = PublicBookingService(
        tenant_session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    catalog = await service.catalog()
    _apply_booking_template_copy(catalog["config"])
    catalog["config"]["custom_html"] = _safe_booking_html(
        str(catalog["config"].get("custom_html") or "")
    )
    branding = await BrandingService(platform_session).manifest_for_context(context)
    return success({
        **catalog,
        "tenant": {
            "id": context.tenant_id,
            "slug": context.slug,
            "hostname": context.hostname,
            "timezone": context.timezone,
        },
        "branding": branding,
    })


@router.get("/booking/availability")
async def public_booking_availability(
    day: date = Query(...),
    service_id: str | None = Query(default=None),
    professional_id: str | None = Query(default=None),
    _: None = Depends(require_tenant_capability("public_booking")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = PublicBookingService(
        session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    return success(await service.availability(
        day=day,
        service_id=service_id,
        professional_id=professional_id,
    ))


@router.post("/booking")
async def create_public_booking(
    payload: PublicBookingCreate,
    _: None = Depends(require_tenant_capability("public_booking")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = PublicBookingService(
        session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    data = await service.book(
        service_id=payload.service_id,
        professional_id=payload.professional_id,
        starts_at=payload.starts_at,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=str(payload.customer_email) if payload.customer_email else None,
    )
    return success(data)

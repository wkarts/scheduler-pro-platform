from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

import bleach
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
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
from app.services.experience_service import ExperienceService
from app.services.global_template_service import GlobalTemplateService
from app.services.html_template_contract import HtmlTemplateContract
from app.services.landing_service import LandingPageService
from app.services.public_booking_service import PublicBookingService
from app.services.public_page_context_service import PublicPageContextService
from app.services.builtin_template_package_service import DEFAULT_TEMPLATE_KEY
from app.services.template_contract import TemplateContract

router = APIRouter()
PUBLIC_LANDING_ASSET_PREFIX = "landing/"
PUBLIC_EXPERIENCE_ASSET_PREFIX = "experience/"
PUBLIC_ASSET_PREFIXES = (PUBLIC_LANDING_ASSET_PREFIX, PUBLIC_EXPERIENCE_ASSET_PREFIX)
PUBLIC_ASSET_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/avif",
    "image/svg+xml",
    "text/css",
    "text/javascript",
    "application/javascript",
    "application/json",
    "font/woff",
    "font/woff2",
    "application/font-woff",
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


async def _ensure_public_booking_enabled(
    *,
    context: TenantContext,
    tenant_session: AsyncSession,
    platform_session: AsyncSession,
) -> dict[str, Any]:
    runtime = await PublicPageContextService(
        context=context, tenant_session=tenant_session, platform_session=platform_session
    ).build()
    if not runtime["pages"]["booking"]["enabled"]:
        raise APIError("PUBLIC_BOOKING_DISABLED", "A Agenda Pública está offline para esta empresa.", 404)
    return runtime


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


def _apply_booking_template_copy(config: dict[str, Any]) -> bool:
    """Aplica somente a cópia visual de um template compatível.

    PR63_FINAL_RUNTIME_FIX: template visual inválido não derruba Booking.
    O motor público continua disponível e o chamador pode aplicar o fallback canônico.
    """
    template = config.get("booking_template")
    if not isinstance(template, dict):
        config.pop("booking_template", None)
        return False
    content = template.get("content")
    if not isinstance(content, dict):
        config.pop("booking_template", None)
        return False
    try:
        TemplateContract.ensure_content("BOOKING", content, strict=False)
    except APIError:
        config.pop("booking_template", None)
        return False
    copy = content.get("copy")
    if not isinstance(copy, dict):
        return True
    title = str(copy.get("title") or "").strip()
    subtitle = str(copy.get("subtitle") or "").strip()
    success_message = str(copy.get("success") or "").strip()
    if title:
        config["title"] = title
    if subtitle:
        config["subtitle"] = subtitle
    if success_message:
        config["success_message"] = success_message
    return True


def _stream(body: Any) -> Iterator[bytes]:
    try:
        yield from body.iter_chunks(chunk_size=64 * 1024)
    finally:
        body.close()


@router.get("/experience/{surface}")
async def public_experience_page(
    surface: str,
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    normalized = surface.strip().upper()
    if normalized not in {"LANDING", "BOOKING"}:
        raise APIError("EXPERIENCE_SURFACE_INVALID", "Use landing ou booking.", 422)
    runtime = await PublicPageContextService(
        context=context, tenant_session=tenant_session, platform_session=platform_session
    ).build()
    page_key = "landing" if normalized == "LANDING" else "booking"
    if not runtime["pages"][page_key]["enabled"]:
        raise APIError("PUBLIC_EXPERIENCE_DISABLED", "Esta página pública está offline.", 404)
    experience = ExperienceService(tenant_session, context)
    result = await experience.document(normalized, published=True)
    if result is None or result.get("version") is None:
        await experience.ensure_default_experience()
        result = await experience.document(normalized, published=True)
    if result is None or result.get("version") is None:
        raise APIError("PUBLIC_EXPERIENCE_NOT_FOUND", "Esta página ainda não foi publicada no Experience Contract v2.", 404)
    branding = await BrandingService(platform_session).manifest_for_context(context)
    return success({"surface": normalized, "page": result["page"], "version": result["version"], "branding": branding, "context": runtime})


# PR63_FINAL_RUNTIME_FIX: alias Landing/Booking para assets já migrados
def _legacy_experience_asset_alias(key: str) -> str | None:
    if not key.startswith(PUBLIC_EXPERIENCE_ASSET_PREFIX):
        return None
    directory, separator, filename = key.rpartition("/")
    if not separator:
        return None
    if filename.startswith("landing-"):
        alternate = "booking-" + filename[len("landing-") :]
    elif filename.startswith("booking-"):
        alternate = "landing-" + filename[len("booking-") :]
    else:
        return None
    return f"{directory}/{alternate}"


async def _get_public_asset_with_legacy_alias(
    context: TenantContext, key: str
) -> dict[str, Any]:
    service = TenantFileService(context)
    try:
        return await service.get_object(key)
    except APIError as original:
        if original.code != "FILE_NOT_FOUND":
            raise
        alternate = _legacy_experience_asset_alias(key)
        if alternate is None:
            raise
        try:
            return await service.get_object(alternate)
        except APIError as fallback_error:
            if fallback_error.code == "FILE_NOT_FOUND":
                raise original
            raise


@router.get("/assets/{key:path}")
async def public_landing_asset(
    key: str,
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    normalized = TenantFileService.normalize_key(key)
    if not (
        normalized.startswith(PUBLIC_LANDING_ASSET_PREFIX)
        or normalized.startswith(PUBLIC_EXPERIENCE_ASSET_PREFIX)
    ):
        raise APIError("PUBLIC_ASSET_NOT_FOUND", "Arquivo público não encontrado.", 404)

    result = await _get_public_asset_with_legacy_alias(context, normalized)
    content_type = str(result.get("ContentType") or "application/octet-stream").lower()
    if content_type not in PUBLIC_ASSET_TYPES:
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


@router.get("/context")
async def public_page_context(
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    runtime = await PublicPageContextService(
        context=context,
        tenant_session=tenant_session,
        platform_session=platform_session,
    ).build()
    return success(runtime)


@router.get("/login")
async def public_login_page(
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    # PR63_FINAL_RUNTIME_FIX: Login é superfície nativa. Este endpoint existe apenas
    # como descriptor para templates/integrações antigas e nunca entrega login.html.
    runtime = await PublicPageContextService(
        context=context,
        tenant_session=tenant_session,
        platform_session=platform_session,
    ).build()
    branding = await BrandingService(platform_session).manifest_for_context(context)
    return success(
        {
            "tenant": runtime["tenant"],
            "branding": branding,
            "context": runtime,
            "login_page": {
                "native": True,
                "route": "/login",
                "template": None,
            },
        }
    )


@router.get("/landing")
async def landing(
    _: None = Depends(require_tenant_capability("landing_pages")),
    slug: str = "home",
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    runtime = await PublicPageContextService(
        context=context,
        tenant_session=tenant_session,
        platform_session=platform_session,
    ).build()
    if not runtime["pages"]["landing"]["enabled"]:
        raise APIError(
            "PUBLIC_LANDING_DISABLED",
            "A Landing Page pública está desativada para esta empresa.",
            404,
        )

    branding = await BrandingService(platform_session).manifest_for_context(context)
    page = await LandingPageService(tenant_session).get_published(slug)
    if page.get("status") == "DEFAULT":
        fallback = await GlobalTemplateService(platform_session).content(
            surface="LANDING",
            key=DEFAULT_TEMPLATE_KEY,
            tenant_id=context.tenant_id,
        )
        page = {
            "slug": slug,
            "status": "DEFAULT",
            "template_key": DEFAULT_TEMPLATE_KEY,
            "version_number": fallback["version"]["version_number"],
            "content": fallback["version"]["content"],
            "fallback": True,
        }
    return success(
        {
            "tenant": runtime["tenant"],
            "branding": branding,
            "context": runtime,
            "landing_page": page,
        }
    )


@router.get("/booking")
async def public_booking_catalog(
    _: None = Depends(require_tenant_capability("public_booking")),
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    runtime = await _ensure_public_booking_enabled(
        context=context,
        tenant_session=tenant_session,
        platform_session=platform_session,
    )
    service = PublicBookingService(
        tenant_session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    catalog = await service.catalog()
    template_valid = _apply_booking_template_copy(catalog["config"])
    if not template_valid:
        fallback = await GlobalTemplateService(platform_session).content(
            surface="BOOKING",
            key=DEFAULT_TEMPLATE_KEY,
            tenant_id=context.tenant_id,
        )
        catalog["config"]["booking_template"] = {
            "key": DEFAULT_TEMPLATE_KEY,
            "version": int(fallback["version"]["version_number"]),
            "content": fallback["version"]["content"],
            "fallback": True,
        }
        _apply_booking_template_copy(catalog["config"])
    catalog["config"]["custom_html"] = _safe_booking_html(
        str(catalog["config"].get("custom_html") or "")
    )
    branding = await BrandingService(platform_session).manifest_for_context(context)
    return success(
        {
            **catalog,
            "tenant": {
                "id": context.tenant_id,
                "slug": context.slug,
                "hostname": context.hostname,
                "timezone": context.timezone,
            },
            "branding": branding,
            "context": runtime,
        }
    )


@router.get("/booking/availability")
async def public_booking_availability(
    day: date = Query(...),
    service_id: str | None = Query(default=None),
    professional_id: str | None = Query(default=None),
    _: None = Depends(require_tenant_capability("public_booking")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await _ensure_public_booking_enabled(context=context, tenant_session=session, platform_session=platform_session)
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
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await _ensure_public_booking_enabled(context=context, tenant_session=session, platform_session=platform_session)
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

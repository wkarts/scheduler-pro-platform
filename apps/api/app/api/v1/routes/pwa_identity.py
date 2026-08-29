from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.deps import get_platform_session, get_tenant_context
from app.core.tenant_context import TenantContext
from app.services.branding_service import BrandingService

router = APIRouter()

CORE_PWA_NAME = "Scheduler Pro"
CORE_PWA_REVISION = "scheduler-pro-core-identity-v1"
CORE_PWA_ICONS = [
    {
        "src": f"/icons/icon-192.png?v={CORE_PWA_REVISION}",
        "sizes": "192x192",
        "type": "image/png",
        "purpose": "any",
    },
    {
        "src": f"/icons/icon-512.png?v={CORE_PWA_REVISION}",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "any",
    },
    {
        "src": f"/icons/maskable-192.png?v={CORE_PWA_REVISION}",
        "sizes": "192x192",
        "type": "image/png",
        "purpose": "maskable",
    },
    {
        "src": f"/icons/maskable-512.png?v={CORE_PWA_REVISION}",
        "sizes": "512x512",
        "type": "image/png",
        "purpose": "maskable",
    },
]


def _dict_value(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _legacy_identity_override(manifest: dict[str, Any]) -> bool:
    settings = _dict_value(manifest, "settings")
    return bool(settings.get("allow_pwa_identity_override", False))


def _allow_tenant_pwa_name(manifest: dict[str, Any]) -> bool:
    settings = _dict_value(manifest, "settings")
    value = settings.get("allow_pwa_name_override")
    return _legacy_identity_override(manifest) if value is None else bool(value)


def _allow_tenant_pwa_icon(manifest: dict[str, Any]) -> bool:
    settings = _dict_value(manifest, "settings")
    value = settings.get("allow_pwa_icon_override")
    return _legacy_identity_override(manifest) if value is None else bool(value)


def _tenant_icons(manifest: dict[str, Any]) -> list[dict[str, str]]:
    assets = _dict_value(manifest, "assets")
    branding_version = int(manifest.get("branding_version") or 0)
    icon_url = str(assets.get("icon_url") or "").strip()
    if not icon_url or icon_url in {"/icons/icon-512.png", "/icons/icon.svg", "/icons/icon.png"}:
        return list(CORE_PWA_ICONS)
    suffix = f"?v={branding_version}" if branding_version else ""
    return [
        {
            "src": f"{icon_url}{suffix}",
            "sizes": "any",
            "type": "image/png",
            "purpose": "any maskable",
        }
    ]


@router.get("/manifest.webmanifest")
async def pwa_manifest(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> JSONResponse:
    manifest = await BrandingService(session).manifest_for_context(context)
    app = _dict_value(manifest, "app")
    theme = _dict_value(manifest, "theme")
    colors = _dict_value(theme, "colors")
    allow_name_override = _allow_tenant_pwa_name(manifest)
    allow_icon_override = _allow_tenant_pwa_icon(manifest)

    if allow_name_override:
        name = str(app.get("public_name") or app.get("name") or CORE_PWA_NAME)
        short_name = name[:30]
    else:
        name = CORE_PWA_NAME
        short_name = CORE_PWA_NAME

    icons = _tenant_icons(manifest) if allow_icon_override else list(CORE_PWA_ICONS)

    identity_parts: list[str] = []
    if allow_name_override:
        identity_parts.append("tenant-name")
    if allow_icon_override:
        identity_parts.append("tenant-icon")
    identity_source = "+".join(identity_parts) if identity_parts else "scheduler-pro"

    branding_version = int(manifest.get("branding_version") or 0)
    payload = {
        "id": f"/{context.slug}",
        "name": name,
        "short_name": short_name,
        "description": app.get("slogan") or "Mais tempo para o que realmente importa.",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": colors.get("background") or "#FFFFFF",
        "theme_color": colors.get("secondary") or "#0B0F1A",
        "icons": icons,
        "categories": ["business", "productivity"],
        "shortcuts": [
            {"name": "Agenda", "url": "/#agenda"},
            {"name": "Página pública", "url": "/pagina"},
            {"name": "Agendar", "url": "/agendar"},
        ],
    }
    return JSONResponse(
        payload,
        media_type="application/manifest+json",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Scheduler-PWA-Identity": identity_source,
            "X-Scheduler-Branding-Version": str(branding_version),
        },
    )

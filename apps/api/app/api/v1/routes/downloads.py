from __future__ import annotations

import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from app.api.deps import get_tenant_context, require_permission, require_tenant_capability
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext

router = APIRouter()
_CACHE_TTL_SECONDS = 300
_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}


def _asset_target(name: str) -> tuple[str, str] | None:
    lower = name.lower()
    if not lower.startswith("scheduler-pro-client-"):
        return None
    if "desktop-windows" in lower and lower.endswith(".tar.gz"):
        return "desktop-windows", "installer-bundle"
    if "desktop-linux" in lower and lower.endswith(".tar.gz"):
        return "desktop-linux", "installer-bundle"
    if "desktop-macos" in lower and lower.endswith(".tar.gz"):
        return "desktop-macos", "installer-bundle"
    if "-android-" in lower and lower.endswith(".apk"):
        return "android", "apk"
    if "-ios-" in lower and lower.endswith(".ipa"):
        return "ios", "ipa-unsigned"
    return None


async def _latest_release_catalog() -> dict[str, Any]:
    now = time.monotonic()
    cached = _cache.get("payload")
    if cached is not None and float(_cache.get("expires_at") or 0) > now:
        return dict(cached)

    repository = os.getenv("GITHUB_ACTIONS_REPOSITORY", "wkarts/scheduler-pro-platform").strip()
    token = os.getenv("GITHUB_ACTIONS_TOKEN", "").strip()
    api_base = os.getenv("GITHUB_ACTIONS_API_BASE_URL", "https://api.github.com").rstrip("/")
    if not repository:
        raise APIError("DISTRIBUTION_REPOSITORY_MISSING", "Catálogo de aplicativos não configurado.", 424)

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "scheduler-pro-distribution",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{api_base}/repos/{repository}/releases/latest",
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise APIError(
            "DISTRIBUTION_CATALOG_UNAVAILABLE",
            "Não foi possível consultar os aplicativos disponíveis agora.",
            424,
        ) from exc

    if response.status_code >= 400:
        raise APIError(
            "DISTRIBUTION_CATALOG_UNAVAILABLE",
            "Não foi possível consultar os aplicativos disponíveis agora.",
            424,
            {"status_code": response.status_code},
        )

    release = response.json()
    artifacts: list[dict[str, Any]] = []
    for asset in release.get("assets", []):
        name = str(asset.get("name") or "")
        mapped = _asset_target(name)
        if mapped is None:
            continue
        target, artifact_type = mapped
        artifacts.append(
            {
                "id": str(asset.get("id") or name),
                "target": target,
                "artifact_type": artifact_type,
                "name": name,
                "download_url": asset.get("browser_download_url"),
                "size_bytes": int(asset.get("size") or 0),
                "created_at": asset.get("created_at"),
                "metadata": {
                    "universal": True,
                    "release": release.get("tag_name"),
                    "content_type": asset.get("content_type"),
                },
            }
        )

    payload = {
        "universal": True,
        "release": release.get("tag_name"),
        "published_at": release.get("published_at"),
        "release_url": release.get("html_url"),
        "artifacts": artifacts,
    }
    _cache["payload"] = payload
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return payload


@router.get("/apps")
async def universal_apps(
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    __: None = Depends(require_tenant_capability("builds")),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    catalog = await _latest_release_catalog()
    return success(
        {
            **catalog,
            "tenant": {
                "id": context.tenant_id,
                "slug": context.slug,
                "hostname": context.hostname,
            },
            "setup": {
                "desktop": "No primeiro acesso, informe a URL deste tenant. Depois o Desktop abre diretamente a WebApp.",
                "mobile": "No primeiro acesso, informe a URL deste tenant. O Mobile usa interface própria e as mesmas APIs.",
            },
        }
    )

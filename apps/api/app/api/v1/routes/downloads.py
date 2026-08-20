from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_tenant_context, require_permission, require_tenant_capability
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.distribution_artifact_service import DistributionArtifactService

router = APIRouter()


def _asset_target(name: str) -> tuple[str, str] | None:
    """Backward-compatible contract used by tests and release tooling."""
    return DistributionArtifactService._asset_target(name)


async def _latest_release_catalog() -> dict[str, Any]:
    service = DistributionArtifactService()
    manifest = await service.read_latest_manifest(required=True)
    assert manifest is not None
    artifacts: list[dict[str, Any]] = []
    for item in manifest.get("artifacts", []):
        artifact = dict(item)
        artifact_id = str(artifact.get("id") or "")
        artifact.pop("object_key", None)
        artifact["download_url"] = f"/api/v1/downloads/apps/{artifact_id}"
        artifacts.append(artifact)
    return {
        "universal": True,
        "source": "internal_bucket",
        "release": manifest.get("release"),
        "published_at": manifest.get("published_at"),
        "synced_at": manifest.get("synced_at"),
        "artifacts": artifacts,
    }


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


@router.get("/apps/{artifact_id}")
async def download_universal_app(
    artifact_id: str,
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    __: None = Depends(require_tenant_capability("builds")),
) -> StreamingResponse:
    service = DistributionArtifactService()
    artifact, stored = await service.get_artifact_object(artifact_id)
    body = stored["Body"]
    filename = str(artifact.get("name") or "scheduler-pro-app")
    content_type = str(stored.get("ContentType") or artifact.get("metadata", {}).get("content_type") or "application/octet-stream")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "private, max-age=300",
        "X-Scheduler-Pro-Release": str(artifact.get("metadata", {}).get("release") or ""),
    }
    content_length = stored.get("ContentLength")
    if content_length is not None:
        headers["Content-Length"] = str(int(content_length))
    return StreamingResponse(
        service.iter_body(body),
        media_type=content_type,
        headers=headers,
    )

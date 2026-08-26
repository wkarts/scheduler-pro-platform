from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_tenant_session
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.landing_service import LandingPageService

router = APIRouter()


class PublishRequest(BaseModel):
    version_id: str | None = None


class DuplicateRequest(BaseModel):
    new_slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


@router.get("/templates")
async def templates() -> dict[str, Any]:
    return success(LandingPageService.templates())


@router.get("/{slug}")
async def editor_state(
    slug: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await LandingPageService(session).editor_state(slug))


@router.get("/{slug}/versions")
async def versions(
    slug: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await LandingPageService(session).versions(slug))


@router.post("/{slug}/draft")
async def save_draft(
    slug: str,
    payload: dict[str, Any] = Body(...),
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    draft = await LandingPageService(session).save_draft(
        slug,
        payload,
        created_by=principal.user_id,
        label="Rascunho manual",
    )
    return success(draft)


@router.post("/{slug}/autosave")
async def autosave(
    slug: str,
    payload: dict[str, Any] = Body(...),
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    draft = await LandingPageService(session).save_draft(
        slug,
        payload,
        created_by=principal.user_id,
        label="Autosave",
    )
    return success(draft)


@router.post("/{slug}/templates/{template_key}")
async def apply_template(
    slug: str,
    template_key: str,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await LandingPageService(session).apply_template(
        slug,
        template_key,
        created_by=principal.user_id,
    )
    return success(data)


@router.post("/{slug}/publish")
async def publish(
    slug: str,
    payload: PublishRequest = Body(default_factory=PublishRequest),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    page = await LandingPageService(session).publish(
        slug,
        version_id=payload.version_id,
    )
    return success(page)


@router.post("/{slug}/versions/{version_id}/restore")
async def restore_version(
    slug: str,
    version_id: str,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await LandingPageService(session).restore(
        slug,
        version_id,
        created_by=principal.user_id,
    )
    return success(data)


@router.post("/{slug}/duplicate")
async def duplicate_page(
    slug: str,
    payload: DuplicateRequest,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await LandingPageService(session).duplicate(
        slug,
        payload.new_slug,
        created_by=principal.user_id,
    )
    return success(data)

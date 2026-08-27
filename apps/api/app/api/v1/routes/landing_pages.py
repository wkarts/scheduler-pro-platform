from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_platform_session,
    get_tenant_context,
    get_tenant_session,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.global_template_service import GlobalTemplateService
from app.services.html_template_contract import HtmlTemplateContract
from app.services.landing_service import LandingPageService
from app.services.template_contract import TemplateContract

router = APIRouter()


class PublishRequest(BaseModel):
    version_id: str | None = None


class DuplicateRequest(BaseModel):
    new_slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def _validate_landing_content(content: dict[str, Any]) -> None:
    if HtmlTemplateContract.is_html_content(content):
        HtmlTemplateContract.ensure_wrapper(content, expected_surface="LANDING")
        return
    TemplateContract.ensure_content("LANDING", content, strict=True)


async def _guard_html_editor_overwrite(
    session: AsyncSession,
    slug: str,
    incoming: dict[str, Any],
) -> None:
    """Impede o editor de blocos de apagar uma Landing HTML sem intenção explícita.

    Trocas de modelo continuam permitidas pelos endpoints de aplicação de template;
    esta barreira protege apenas os saves/autosaves genéricos do editor visual.
    """
    current = await LandingPageService(session).editor_state(slug)
    current_content = current.get("content")
    if (
        isinstance(current_content, dict)
        and HtmlTemplateContract.is_html_content(current_content)
        and not HtmlTemplateContract.is_html_content(incoming)
    ):
        raise APIError(
            "LANDING_HTML_EDITOR_REQUIRED",
            "Esta página usa um modelo HTML. Edite ou substitua o HTML pela área de modelos; para trocar para um modelo visual por blocos, aplique explicitamente outro modelo.",
            409,
        )


@router.get("/templates")
async def templates(
    context: TenantContext = Depends(get_tenant_context),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    legacy = [
        {**item, "source": "builtin", "version": None}
        for item in LandingPageService.templates()
    ]
    global_rows = await GlobalTemplateService(platform).list(
        surface="LANDING",
        tenant_id=context.tenant_id,
    )
    global_templates = [
        {
            "key": row["key"],
            "name": row["name"],
            "description": row.get("description") or "Modelo global da plataforma.",
            "segment": row.get("segment") or "global",
            "source": "global",
            "version": row.get("published_version"),
            "template_id": row["id"],
        }
        for row in global_rows
    ]
    return success(global_templates + legacy)


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
    _validate_landing_content(payload)
    await _guard_html_editor_overwrite(session, slug, payload)
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
    _validate_landing_content(payload)
    await _guard_html_editor_overwrite(session, slug, payload)
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
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    global_service = GlobalTemplateService(platform)
    try:
        template = await global_service.content(
            surface="LANDING",
            key=template_key,
            tenant_id=context.tenant_id,
        )
    except APIError as exc:
        if exc.code != "GLOBAL_TEMPLATE_NOT_FOUND":
            raise
        data = await LandingPageService(session).apply_template(
            slug,
            template_key,
            created_by=principal.user_id,
        )
        return success(data)

    template_content = template["version"]["content"]
    _validate_landing_content(template_content)
    draft = await LandingPageService(session).save_draft(
        slug,
        template_content,
        created_by=principal.user_id,
        label=f"Modelo global: {template['name']} v{template['version']['version_number']}",
    )
    source_key = f"global:{template['key']}@{template['version']['version_number']}"
    await session.execute(
        text("update landing_pages set template_key=:key where slug=:slug"),
        {"key": source_key, "slug": slug},
    )
    await session.commit()
    return success(
        {
            **draft,
            "template_key": source_key,
            "global_template_id": template["id"],
            "global_template_version": template["version"]["version_number"],
        }
    )


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

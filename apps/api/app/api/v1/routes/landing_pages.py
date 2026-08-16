from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.services.landing_service import LandingPageService

router = APIRouter()


class LandingContent(BaseModel):
    version: int = 1
    sections: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/{slug}")
async def editor_state(
    slug: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                select lp.id::text, lp.slug, lp.status, lp.current_version_id::text,
                       lpv.id::text as latest_version_id, lpv.version_number,
                       lpv.content, lpv.created_at
                from landing_pages lp
                left join lateral (
                  select *
                  from landing_page_versions
                  where landing_page_id=lp.id
                  order by version_number desc
                  limit 1
                ) lpv on true
                where lp.slug=:slug
                """
            ),
            {"slug": slug},
        )
    ).mappings().first()
    if row is None:
        return success(
            {
                "slug": slug,
                "status": "NEW",
                "content": {"version": 1, "sections": []},
                "versions": [],
            }
        )

    versions = (
        await session.execute(
            text(
                """
                select id::text, version_number, created_at
                from landing_page_versions
                where landing_page_id=:id::uuid
                order by version_number desc
                limit 50
                """
            ),
            {"id": row["id"]},
        )
    ).mappings().all()
    data = dict(row)
    data["versions"] = [dict(version) for version in versions]
    return success(data)


@router.post("/{slug}/draft")
async def save_draft(
    slug: str,
    payload: LandingContent,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    draft = await LandingPageService(session).save_draft(slug, payload.model_dump())
    return success(draft)


@router.post("/{slug}/publish")
async def publish(
    slug: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    page = await LandingPageService(session).publish(slug)
    return success(page)

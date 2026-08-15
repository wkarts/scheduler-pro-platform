from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.services.landing_service import LandingPageService

router = APIRouter()


class LandingContent(BaseModel):
    version: int = 1
    sections: list[dict] = Field(default_factory=list)


@router.post("/{slug}/draft")
async def save_draft(slug: str, payload: LandingContent, session: AsyncSession = Depends(get_tenant_session)):
    service = LandingPageService(session)
    version = await service.save_draft(slug, payload.model_dump())
    return success(version)


@router.post("/{slug}/publish")
async def publish(slug: str, session: AsyncSession = Depends(get_tenant_session)):
    service = LandingPageService(session)
    page = await service.publish(slug)
    return success(page)

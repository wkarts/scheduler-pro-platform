from typing import Any

import bleach
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LandingPageStatus
from app.db.models_tenant import LandingPage, LandingPageVersion

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "section",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "p",
    "img",
    "a",
    "strong",
    "em",
    "ul",
    "li",
    "br",
    "button",
}
ALLOWED_ATTRS = {
    "*": ["class", "id", "data-section"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "loading"],
}

DEFAULT_LANDING = {
    "version": 1,
    "sections": [
        {
            "type": "hero",
            "title": "Agende seu horário online",
            "subtitle": "Escolha serviço, profissional e melhor horário sem esperar resposta manual.",
            "cta_label": "Agendar agora",
        },
        {
            "type": "features",
            "items": ["Confirmação por WhatsApp", "Serviços e profissionais", "Página própria da empresa"],
        },
    ],
}


class LandingPageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def sanitize(self, content: dict[str, Any]) -> dict[str, Any]:
        for section in content.get("sections", []):
            if section.get("type") == "custom_html" and "html" in section:
                section["html"] = bleach.clean(
                    section["html"],
                    tags=ALLOWED_TAGS,
                    attributes=ALLOWED_ATTRS,
                    strip=True,
                )
        return content

    async def save_draft(self, slug: str, content: dict[str, Any]) -> dict[str, object]:
        page = (await self.session.execute(select(LandingPage).where(LandingPage.slug == slug))).scalar_one_or_none()
        if page is None:
            page = LandingPage(slug=slug, status=LandingPageStatus.draft.value)
            self.session.add(page)
            await self.session.flush()
        versions = (
            await self.session.execute(
                select(LandingPageVersion).where(LandingPageVersion.landing_page_id == page.id)
            )
        ).scalars().all()
        version = LandingPageVersion(
            landing_page_id=page.id,
            version_number=len(versions) + 1,
            content=self.sanitize(content),
        )
        self.session.add(version)
        await self.session.commit()
        return {"landing_page_id": page.id, "version_id": version.id, "version_number": version.version_number}

    async def publish(self, slug: str) -> dict[str, object]:
        page = (await self.session.execute(select(LandingPage).where(LandingPage.slug == slug))).scalar_one()
        version = (
            await self.session.execute(
                select(LandingPageVersion)
                .where(LandingPageVersion.landing_page_id == page.id)
                .order_by(desc(LandingPageVersion.version_number))
                .limit(1)
            )
        ).scalar_one()
        page.status = LandingPageStatus.published.value
        page.current_version_id = version.id
        await self.session.commit()
        return {"id": page.id, "status": page.status, "current_version_id": page.current_version_id}

    async def get_published(self, slug: str = "home") -> dict[str, Any]:
        page = (await self.session.execute(select(LandingPage).where(LandingPage.slug == slug))).scalar_one_or_none()
        if page is None or page.status != LandingPageStatus.published.value:
            return {"slug": slug, "status": "DEFAULT", "content": DEFAULT_LANDING}
        query = select(LandingPageVersion).where(LandingPageVersion.landing_page_id == page.id)
        if page.current_version_id:
            query = query.where(LandingPageVersion.id == page.current_version_id)
        query = query.order_by(desc(LandingPageVersion.version_number)).limit(1)
        version = (await self.session.execute(query)).scalar_one_or_none()
        if version is None:
            return {"slug": slug, "status": "DEFAULT", "content": DEFAULT_LANDING}
        return {
            "id": str(page.id),
            "slug": page.slug,
            "status": page.status,
            "version_id": str(version.id),
            "version_number": version.version_number,
            "content": version.content,
        }

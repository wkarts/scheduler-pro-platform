import bleach
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LandingPageStatus
from app.db.models_tenant import LandingPage, LandingPageVersion

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {"section", "div", "span", "h1", "h2", "h3", "p", "img", "a", "strong", "em", "ul", "li", "br"}
ALLOWED_ATTRS = {"*": ["class", "id"], "a": ["href", "title", "target"], "img": ["src", "alt", "loading"]}


class LandingPageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def sanitize(self, content: dict) -> dict:
        for section in content.get("sections", []):
            if section.get("type") == "custom_html" and "html" in section:
                section["html"] = bleach.clean(section["html"], tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        return content

    async def save_draft(self, slug: str, content: dict) -> dict:
        page = (await self.session.execute(select(LandingPage).where(LandingPage.slug == slug))).scalar_one_or_none()
        if page is None:
            page = LandingPage(slug=slug, status=LandingPageStatus.draft.value)
            self.session.add(page)
            await self.session.flush()
        count = (await self.session.execute(select(LandingPageVersion).where(LandingPageVersion.landing_page_id == page.id))).scalars().all()
        version = LandingPageVersion(landing_page_id=page.id, version_number=len(count) + 1, content=self.sanitize(content))
        self.session.add(version)
        await self.session.commit()
        return {"landing_page_id": page.id, "version_id": version.id, "version_number": version.version_number}

    async def publish(self, slug: str) -> dict:
        page = (await self.session.execute(select(LandingPage).where(LandingPage.slug == slug))).scalar_one()
        page.status = LandingPageStatus.published.value
        await self.session.commit()
        return {"id": page.id, "status": page.status}

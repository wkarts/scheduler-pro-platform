from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

import bleach
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LandingPageStatus
from app.core.errors import APIError
from app.db.models_tenant import LandingPage, LandingPageVersion
from app.services.landing_templates import list_templates, template_content

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "section",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "img",
    "a",
    "strong",
    "em",
    "small",
    "ul",
    "ol",
    "li",
    "br",
    "button",
    "figure",
    "figcaption",
}
ALLOWED_ATTRS = {
    "*": ["class", "id", "data-section", "aria-label", "role"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "loading", "width", "height"],
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
            "items": [
                "Confirmação por WhatsApp",
                "Serviços e profissionais",
                "Página própria da empresa",
            ],
        },
    ],
}

URL_FIELDS = {
    "url",
    "href",
    "src",
    "image",
    "image_url",
    "logo",
    "logo_url",
    "video",
    "video_url",
    "share_image",
    "canonical_url",
}


class LandingPageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _safe_url(value: str, *, allow_data_image: bool = False) -> str:
        candidate = value.strip()
        if not candidate:
            return ""
        lowered = candidate.lower()
        if lowered.startswith(("javascript:", "vbscript:", "data:text/html")):
            return ""
        if allow_data_image and lowered.startswith("data:image/"):
            return candidate
        if candidate.startswith(("/", "#")):
            return candidate
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https", "mailto", "tel"}:
            return candidate
        return ""

    @classmethod
    def _sanitize_value(cls, key: str, value: Any) -> Any:
        normalized_key = key.strip().lower()
        if normalized_key.startswith("on") or normalized_key in {
            "script",
            "javascript",
            "dangerouslysetinnerhtml",
            "innerhtml",
        }:
            return None
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for child_key, child_value in value.items():
                clean = cls._sanitize_value(str(child_key), child_value)
                if clean is not None:
                    sanitized[str(child_key)] = clean
            return sanitized
        if isinstance(value, list):
            return [
                clean
                for index, item in enumerate(value)
                if (clean := cls._sanitize_value(f"item_{index}", item)) is not None
            ]
        if isinstance(value, str):
            if normalized_key in URL_FIELDS:
                return cls._safe_url(
                    value,
                    allow_data_image=normalized_key in {"src", "image", "image_url", "logo", "logo_url", "share_image"},
                )
            if normalized_key in {"html", "custom_html"}:
                return bleach.clean(
                    value,
                    tags=ALLOWED_TAGS,
                    attributes=ALLOWED_ATTRS,
                    protocols={"http", "https", "mailto", "tel"},
                    strip=True,
                )
            # Texto comum não aceita marcação executável. Mantemos caracteres e
            # conteúdo editorial, removendo apenas tags HTML.
            return bleach.clean(value, tags=set(), attributes={}, strip=True)
        return value

    def sanitize(self, content: dict[str, Any]) -> dict[str, Any]:
        clean = self._sanitize_value("content", deepcopy(content))
        return clean if isinstance(clean, dict) else {"version": 2, "blocks": []}

    async def _lock_page(self, slug: str) -> None:
        await self.session.execute(
            text("select pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"scheduler-pro:landing-page:{slug}"},
        )

    async def _page(self, slug: str, *, create: bool = False) -> LandingPage | None:
        page = (
            await self.session.execute(
                select(LandingPage).where(LandingPage.slug == slug)
            )
        ).scalar_one_or_none()
        if page is None and create:
            page = LandingPage(slug=slug, status=LandingPageStatus.draft.value)
            self.session.add(page)
            await self.session.flush()
        return page

    async def _next_version_number(self, page_id: str) -> int:
        maximum = await self.session.scalar(
            select(func.max(LandingPageVersion.version_number)).where(
                LandingPageVersion.landing_page_id == page_id
            )
        )
        return int(maximum or 0) + 1

    async def _create_version(
        self,
        page: LandingPage,
        content: dict[str, Any],
        *,
        created_by: str | None = None,
        label: str | None = None,
        source_version_id: str | None = None,
    ) -> LandingPageVersion:
        version = LandingPageVersion(
            landing_page_id=page.id,
            version_number=await self._next_version_number(str(page.id)),
            content=self.sanitize(content),
            created_by=created_by,
            label=label,
            source_version_id=source_version_id,
        )
        self.session.add(version)
        await self.session.flush()
        page.draft_version_id = version.id
        return version

    async def save_draft(
        self,
        slug: str,
        content: dict[str, Any],
        *,
        created_by: str | None = None,
        label: str | None = "Rascunho",
    ) -> dict[str, object]:
        await self._lock_page(slug)
        page = await self._page(slug, create=True)
        assert page is not None
        version = await self._create_version(
            page,
            content,
            created_by=created_by,
            label=label,
        )
        await self.session.commit()
        return {
            "landing_page_id": str(page.id),
            "version_id": str(version.id),
            "version_number": version.version_number,
            "status": page.status,
            "published_version_id": str(page.current_version_id) if page.current_version_id else None,
        }

    async def apply_template(
        self,
        slug: str,
        template_key: str,
        *,
        created_by: str | None = None,
    ) -> dict[str, object]:
        try:
            content = template_content(template_key)
        except KeyError as exc:
            raise APIError(
                "LANDING_TEMPLATE_NOT_FOUND",
                "Modelo de agenda pública não encontrado.",
                404,
            ) from exc
        await self._lock_page(slug)
        page = await self._page(slug, create=True)
        assert page is not None
        version = await self._create_version(
            page,
            content,
            created_by=created_by,
            label=f"Modelo: {template_key}",
        )
        page.template_key = template_key
        # Não toca current_version_id: a página que está no ar permanece intacta.
        await self.session.commit()
        return {
            "landing_page_id": str(page.id),
            "template_key": template_key,
            "draft_version_id": str(version.id),
            "version_number": version.version_number,
            "published_version_id": str(page.current_version_id) if page.current_version_id else None,
        }

    async def publish(
        self,
        slug: str,
        *,
        version_id: str | None = None,
    ) -> dict[str, object]:
        await self._lock_page(slug)
        page = await self._page(slug)
        if page is None:
            raise APIError("LANDING_PAGE_NOT_FOUND", "Página pública não encontrada.", 404)
        target_id = version_id or (
            str(page.draft_version_id) if page.draft_version_id else None
        )
        query = select(LandingPageVersion).where(
            LandingPageVersion.landing_page_id == page.id
        )
        if target_id:
            query = query.where(LandingPageVersion.id == target_id)
        else:
            query = query.order_by(desc(LandingPageVersion.version_number)).limit(1)
        version = (await self.session.execute(query)).scalar_one_or_none()
        if version is None:
            raise APIError(
                "LANDING_VERSION_NOT_FOUND",
                "Versão da página pública não encontrada.",
                404,
            )
        page.status = LandingPageStatus.published.value
        page.current_version_id = version.id
        page.draft_version_id = version.id
        await self.session.commit()
        return {
            "id": str(page.id),
            "status": page.status,
            "current_version_id": str(page.current_version_id),
            "version_number": version.version_number,
        }

    async def versions(self, slug: str, *, limit: int = 100) -> list[dict[str, Any]]:
        page = await self._page(slug)
        if page is None:
            return []
        rows = (
            await self.session.execute(
                select(LandingPageVersion)
                .where(LandingPageVersion.landing_page_id == page.id)
                .order_by(desc(LandingPageVersion.version_number))
                .limit(max(1, min(200, limit)))
            )
        ).scalars().all()
        return [
            {
                "id": str(item.id),
                "version_number": item.version_number,
                "label": item.label,
                "source_version_id": str(item.source_version_id) if item.source_version_id else None,
                "created_at": item.created_at,
                "published": str(item.id) == str(page.current_version_id),
                "draft": str(item.id) == str(page.draft_version_id),
            }
            for item in rows
        ]

    async def restore(
        self,
        slug: str,
        version_id: str,
        *,
        created_by: str | None = None,
    ) -> dict[str, object]:
        await self._lock_page(slug)
        page = await self._page(slug)
        if page is None:
            raise APIError("LANDING_PAGE_NOT_FOUND", "Página pública não encontrada.", 404)
        source = (
            await self.session.execute(
                select(LandingPageVersion).where(
                    LandingPageVersion.id == version_id,
                    LandingPageVersion.landing_page_id == page.id,
                )
            )
        ).scalar_one_or_none()
        if source is None:
            raise APIError("LANDING_VERSION_NOT_FOUND", "Versão não encontrada.", 404)
        restored = await self._create_version(
            page,
            deepcopy(source.content),
            created_by=created_by,
            label=f"Restaurado da versão {source.version_number}",
            source_version_id=str(source.id),
        )
        # Restauração cria rascunho; publicação continua sendo decisão explícita.
        await self.session.commit()
        return {
            "version_id": str(restored.id),
            "version_number": restored.version_number,
            "source_version_id": str(source.id),
            "published_version_id": str(page.current_version_id) if page.current_version_id else None,
        }

    async def duplicate(
        self,
        slug: str,
        new_slug: str,
        *,
        created_by: str | None = None,
    ) -> dict[str, object]:
        source_page = await self._page(slug)
        if source_page is None:
            raise APIError("LANDING_PAGE_NOT_FOUND", "Página pública não encontrada.", 404)
        existing = await self._page(new_slug)
        if existing is not None:
            raise APIError("LANDING_SLUG_EXISTS", "Já existe uma página com este endereço.", 409)
        source_query = select(LandingPageVersion).where(
            LandingPageVersion.landing_page_id == source_page.id
        )
        if source_page.draft_version_id:
            source_query = source_query.where(
                LandingPageVersion.id == source_page.draft_version_id
            )
        else:
            source_query = source_query.order_by(desc(LandingPageVersion.version_number)).limit(1)
        source = (await self.session.execute(source_query)).scalar_one_or_none()
        if source is None:
            raise APIError("LANDING_VERSION_NOT_FOUND", "Página sem versão para duplicar.", 409)
        await self._lock_page(new_slug)
        new_page = await self._page(new_slug, create=True)
        assert new_page is not None
        new_page.template_key = source_page.template_key
        new_page.settings = deepcopy(source_page.settings or {})
        version = await self._create_version(
            new_page,
            deepcopy(source.content),
            created_by=created_by,
            label=f"Duplicada de {slug}",
            source_version_id=str(source.id),
        )
        await self.session.commit()
        return {
            "landing_page_id": str(new_page.id),
            "slug": new_slug,
            "draft_version_id": str(version.id),
            "version_number": version.version_number,
        }

    async def editor_state(self, slug: str) -> dict[str, Any]:
        page = await self._page(slug)
        if page is None:
            return {
                "slug": slug,
                "status": "NEW",
                "template_key": None,
                "content": {"version": 2, "blocks": []},
                "published_content": None,
                "versions": [],
            }

        draft_query = select(LandingPageVersion).where(
            LandingPageVersion.landing_page_id == page.id
        )
        if page.draft_version_id:
            draft_query = draft_query.where(
                LandingPageVersion.id == page.draft_version_id
            )
        else:
            draft_query = draft_query.order_by(desc(LandingPageVersion.version_number)).limit(1)
        draft = (await self.session.execute(draft_query)).scalar_one_or_none()

        published = None
        if page.current_version_id:
            published = (
                await self.session.execute(
                    select(LandingPageVersion).where(
                        LandingPageVersion.id == page.current_version_id,
                        LandingPageVersion.landing_page_id == page.id,
                    )
                )
            ).scalar_one_or_none()

        return {
            "id": str(page.id),
            "slug": page.slug,
            "status": page.status,
            "template_key": page.template_key,
            "settings": page.settings or {},
            "current_version_id": str(page.current_version_id) if page.current_version_id else None,
            "draft_version_id": str(page.draft_version_id) if page.draft_version_id else None,
            "version_number": draft.version_number if draft else None,
            "content": deepcopy(draft.content) if draft else {"version": 2, "blocks": []},
            "published_content": deepcopy(published.content) if published else None,
            "versions": await self.versions(slug),
        }

    async def get_published(self, slug: str = "home") -> dict[str, Any]:
        page = await self._page(slug)
        if page is None or page.status != LandingPageStatus.published.value:
            return {"slug": slug, "status": "DEFAULT", "content": DEFAULT_LANDING}
        query = select(LandingPageVersion).where(
            LandingPageVersion.landing_page_id == page.id
        )
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
            "template_key": page.template_key,
            "version_id": str(version.id),
            "version_number": version.version_number,
            "content": deepcopy(version.content),
        }

    @staticmethod
    def templates() -> list[dict[str, Any]]:
        return list_templates()

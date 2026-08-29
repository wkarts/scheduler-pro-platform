from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import TenantContext

VISUAL_BUILDER_VERSION = "2.4.0"


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "sim", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "nao", "não", "off", "disabled"}:
            return False
    return default


class PublicPageContextService:
    """Contexto canônico compartilhado entre editor, Preview e publicação."""

    def __init__(
        self,
        *,
        context: TenantContext,
        tenant_session: AsyncSession,
        platform_session: AsyncSession,
    ) -> None:
        self.context = context
        self.tenant_session = tenant_session
        self.platform_session = platform_session

    async def build(self) -> dict[str, Any]:
        public_setting_keys = [
            "landing_page_enabled",
            "public_booking_enabled",
            "public_login_enabled",
            "show_login_on_landing",
            "show_booking_on_landing",
            "show_contact_on_landing",
            "show_whatsapp_on_landing",
            "booking_page_template_key",
            "login_page_template_key",
            "marketing_analytics",
            "pwa_open_mode",
        ]
        setting_rows = (
            await self.tenant_session.execute(
                text(
                    "select key, value from tenant_settings "
                    "where key = any(cast(:keys as text[])) order by key"
                ),
                {"keys": public_setting_keys},
            )
        ).mappings().all()
        preferences = {str(row["key"]): row["value"] for row in setting_rows}

        capability_rows = (
            await self.platform_session.execute(
                text(
                    "select capability_key, enabled, config from tenant_capabilities "
                    "where tenant_id=cast(:tenant_id as uuid) order by capability_key"
                ),
                {"tenant_id": self.context.tenant_id},
            )
        ).mappings().all()
        capabilities = {
            str(row["capability_key"]): {
                "enabled": bool(row["enabled"]),
                "config": row.get("config") or {},
            }
            for row in capability_rows
        }

        landing_capability = bool(
            capabilities.get("landing_pages", {}).get("enabled")
        )
        booking_capability = bool(
            capabilities.get("public_booking", {}).get("enabled")
        )
        landing_enabled = landing_capability and _bool(
            preferences.get("landing_page_enabled"),
            True,
        )
        booking_enabled = booking_capability and _bool(
            preferences.get("public_booking_enabled"),
            False,
        )
        login_enabled = _bool(preferences.get("public_login_enabled"), True)

        show_login = login_enabled and _bool(
            preferences.get("show_login_on_landing"),
            False,
        )
        show_booking = booking_enabled and _bool(
            preferences.get("show_booking_on_landing"),
            True,
        )
        show_contact = _bool(preferences.get("show_contact_on_landing"), True)
        show_whatsapp = _bool(preferences.get("show_whatsapp_on_landing"), True)

        return {
            "schema": "scheduler-pro-public-page-context/v1",
            "visual_builder_version": VISUAL_BUILDER_VERSION,
            "tenant": {
                "id": self.context.tenant_id,
                "slug": self.context.slug,
                "hostname": self.context.hostname,
                "timezone": self.context.timezone,
            },
            "pages": {
                "landing": {"route": "/pagina", "enabled": landing_enabled},
                "booking": {"route": "/agendar", "enabled": booking_enabled},
                "login": {"route": "/login", "enabled": login_enabled},
            },
            "features": {
                "landing": landing_enabled,
                "booking": booking_enabled,
                "public_booking": booking_enabled,
                "public_schedule_enabled": booking_enabled,
                "login": login_enabled,
                "show_login": show_login,
                "show_booking": show_booking,
                "show_contact": show_contact,
                "show_whatsapp": show_whatsapp,
            },
            "capabilities": capabilities,
            "preferences": {
                "landing_page_enabled": landing_enabled,
                "public_booking_enabled": booking_enabled,
                "public_login_enabled": login_enabled,
                "show_login_on_landing": show_login,
                "show_booking_on_landing": show_booking,
                "show_contact_on_landing": show_contact,
                "show_whatsapp_on_landing": show_whatsapp,
                "booking_page_template_key": preferences.get(
                    "booking_page_template_key"
                ),
                "login_page_template_key": preferences.get(
                    "login_page_template_key"
                ),
                "marketing_analytics": preferences.get("marketing_analytics") or {},
                "pwa_open_mode": preferences.get("pwa_open_mode") or "AUTO",
            },
        }

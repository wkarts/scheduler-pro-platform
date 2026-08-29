from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

from app.api.v1.routes.schedule import BlockedPeriodPayload, BusinessHourPayload
from app.api.v1.routes.services import ServiceCreate, ServiceUpdate


API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
WEB_ROOT = REPO_ROOT / "apps" / "web"


def test_service_duration_can_be_variable() -> None:
    assert ServiceCreate(name="Atendimento variável", duration_minutes=0).duration_minutes == 0
    assert ServiceUpdate(duration_minutes=0).duration_minutes == 0


def test_business_hours_accept_evening_shift_and_blocked_period_updates() -> None:
    shift = BusinessHourPayload(
        professional_id=None,
        day_of_week=1,
        opens_at=time(17, 30),
        closes_at=time(22, 0),
    )
    assert shift.opens_at == time(17, 30)
    assert shift.closes_at == time(22, 0)

    blocked = BlockedPeriodPayload(
        professional_id=None,
        starts_at=datetime(2026, 8, 29, 18, 0),
        ends_at=datetime(2026, 8, 29, 20, 0),
        reason="Atendimento externo",
    )
    assert blocked.ends_at > blocked.starts_at


def test_mobile_drawer_renders_labels_even_when_desktop_sidebar_is_collapsed() -> None:
    source = (WEB_ROOT / "src" / "TenantConsole.vue").read_text(encoding="utf-8")
    assert 'v-if="!collapsed || mobileOpen">{{ item.label }}' in source
    assert 'v-if="!collapsed || mobileOpen">Sair' in source


def test_mobile_calendar_uses_minmax_columns_and_legacy_appointments_filter_by_start() -> None:
    css = (WEB_ROOT / "src" / "tenant-mobile-native.css").read_text(encoding="utf-8")
    assert "repeat(7, minmax(0, 1fr))" in css
    assert "min-width: 0 !important" in css

    service = (API_ROOT / "app" / "services" / "appointment_service.py").read_text(encoding="utf-8")
    assert 'a.starts_at >= :range_start and a.starts_at < :range_end' in service
    assert "a.ends_at is null or a.ends_at <= a.starts_at" in service


def test_pwa_update_and_branding_manifest_bypass_stale_cache() -> None:
    pwa = (WEB_ROOT / "src" / "pwa.ts").read_text(encoding="utf-8")
    assert "updateViaCache: 'none'" in pwa

    sw = (WEB_ROOT / "public" / "sw.js").read_text(encoding="utf-8")
    assert "avb-2.4.0-final-mobile-agenda-v5" in sw

    branding = (API_ROOT / "app" / "api" / "v1" / "routes" / "branding.py").read_text(encoding="utf-8")
    assert '"Cache-Control": "no-store, max-age=0"' in branding
    assert "avb240-brand-v2" in branding


def test_multitenant_ci_retries_transient_buildkit_eof() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "integration-tests.yml").read_text(encoding="utf-8")
    assert "Build development API images with retry" in workflow
    assert "for attempt in 1 2 3" in workflow
    assert "up --no-build -d" in workflow

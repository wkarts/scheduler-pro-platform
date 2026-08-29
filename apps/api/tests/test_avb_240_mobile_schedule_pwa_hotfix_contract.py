from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

from app.api.v1.routes.schedule import BlockedPeriodPayload, BusinessHourPayload
from app.api.v1.routes.services import ServiceCreate, ServiceUpdate


API_ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path | None:
    for candidate in (API_ROOT, *API_ROOT.parents):
        if (candidate / "apps" / "api").is_dir() and (candidate / "apps" / "web").is_dir():
            return candidate
    return None


REPO_ROOT = _repo_root()
WEB_ROOT = REPO_ROOT / "apps" / "web" if REPO_ROOT is not None else None


def _web_root() -> Path:
    if WEB_ROOT is None or not WEB_ROOT.is_dir():
        import pytest
        pytest.skip("Fontes Web não fazem parte da imagem isolada da API.")
    return WEB_ROOT



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
    web = _web_root()
    source = (web / "src" / "TenantConsole.vue").read_text(encoding="utf-8")
    assert 'v-if="!collapsed || mobileOpen">{{ item.label }}' in source
    assert 'v-if="!collapsed || mobileOpen">Sair' in source


def test_mobile_calendar_uses_minmax_columns_and_legacy_appointments_filter_by_start() -> None:
    web = _web_root()
    css = (web / "src" / "tenant-mobile-native.css").read_text(encoding="utf-8")
    assert "repeat(7, minmax(0, 1fr))" in css
    assert "min-width: 0 !important" in css

    service = (API_ROOT / "app" / "services" / "appointment_service.py").read_text(encoding="utf-8")
    assert 'a.starts_at >= :range_start and a.starts_at < :range_end' in service
    assert "a.ends_at is null or a.ends_at <= a.starts_at" in service


def test_pwa_update_and_branding_manifest_bypass_stale_cache() -> None:
    web = _web_root()
    pwa = (web / "src" / "pwa.ts").read_text(encoding="utf-8")
    assert "updateViaCache: 'none'" in pwa

    sw = (web / "public" / "sw.js").read_text(encoding="utf-8")
    assert "avb-2.4.0-final-mobile-agenda-v5" in sw

    branding = (API_ROOT / "app" / "api" / "v1" / "routes" / "branding.py").read_text(encoding="utf-8")
    assert '"Cache-Control": "no-store, max-age=0"' in branding
    assert "avb240-brand-v2" in branding


def test_multitenant_ci_keeps_the_stable_stack_workflow() -> None:
    if REPO_ROOT is None:
        import pytest
        pytest.skip("Workflow do monorepo não faz parte da imagem isolada da API.")
    workflow = (REPO_ROOT / ".github" / "workflows" / "integration-tests.yml").read_text(encoding="utf-8")
    assert "docker compose -f deployments/development/docker-compose.yml up --build -d" in workflow
    assert "Full integration suite single process regression" in workflow
    assert "Migration downgrade and re-upgrade" in workflow
    assert "Build development API images with retry" not in workflow
    assert "up --no-build -d" not in workflow

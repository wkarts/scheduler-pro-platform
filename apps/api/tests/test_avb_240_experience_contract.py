from pathlib import Path

from app.services.experience_contract_service import ExperienceContractService

ROOT = Path(__file__).resolve().parents[3]
API = ROOT / "apps" / "api"
WEB = ROOT / "apps" / "web"


def test_default_template_migrates_to_experience_v2_without_login_template() -> None:
    archive = API / "resources" / "template-packages" / "scheduler-pro-padrao-generico.zip"
    parsed = ExperienceContractService.parse_archive(archive.read_bytes())
    assert parsed.package_key == "scheduler-pro-padrao-generico"
    assert parsed.landing_html
    assert parsed.booking_html
    assert len(parsed.assets) >= 1
    assert parsed.bindings["schema"] == "argws-bindings/v1"
    assert "business.name" in parsed.bindings["bindings"]
    assert "data-sp-bind" in parsed.landing_html
    assert any("Login legado foi ignorado" in warning for warning in parsed.warnings)


def test_schedule_crud_supports_edit_delete_and_blocked_period_update() -> None:
    source = (API / "app" / "api" / "v1" / "routes" / "schedule.py").read_text()
    assert '@router.put("/business-hours/{business_hour_id}")' in source
    assert '@router.delete("/business-hours/{business_hour_id}")' in source
    assert '@router.put("/blocked-periods/{blocked_period_id}")' in source
    assert '@router.delete("/blocked-periods/{blocked_period_id}")' in source
    assert ":id::uuid" not in source
    assert "cast(:id as uuid)" in source


def test_legacy_appointments_are_not_lost_by_inner_joins_or_missing_end_time() -> None:
    source = (API / "app" / "services" / "appointment_service.py").read_text()
    assert "left join customers" in source
    assert "left join services" in source
    assert "left join professionals" in source
    assert "Cliente legado" in source
    assert "Agenda geral" in source
    assert "coalesce(a.ends_at, a.starts_at + interval '60 minutes')" in source


def test_mobile_shell_and_calendar_do_not_require_desktop_width() -> None:
    shell = (WEB / "src" / "TenantConsole.vue").read_text()
    css = (WEB / "src" / "tenant-shell-contract.css").read_text()
    calendar = (WEB / "src" / "TenantAgendaCenter.vue").read_text()
    assert "toggleShellMenu" in shell
    assert "mobile-nav-backdrop" in shell
    assert "sp-mobile-nav-open" in css
    assert ".sp-calendar-grid,.sp-weekdays{min-width:0;width:100%}" in calendar


def test_branding_ui_supports_light_dark_pwa_favicon_and_native_login() -> None:
    source = (WEB / "src" / "TenantVisualPageBuilder.vue").read_text()
    assert "Logo claro" in source
    assert "Logo escuro" in source
    assert "Ícone PWA" in source
    assert "Favicon" in source
    assert "Login não usa template HTML" in source

from pathlib import Path

import pytest

from app.services.experience_contract_service import ExperienceContractService

API = Path(__file__).resolve().parents[1]
MONOREPO = API.parents[1] if API.parent.name == "apps" else None
WEB = MONOREPO / "apps" / "web" if MONOREPO is not None else None

def _web_root() -> Path:
    if WEB is None or not WEB.is_dir():
        pytest.skip("Fontes Web não fazem parte da imagem isolada da API.")
    return WEB


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
    assert "a.ends_at is null or a.ends_at <= a.starts_at" in source


def test_mobile_shell_and_calendar_do_not_require_desktop_width() -> None:
    web = _web_root()
    shell = (web / "src" / "TenantConsole.vue").read_text()
    css = (web / "src" / "tenant-shell-contract.css").read_text()
    calendar = (web / "src" / "TenantAgendaCenter.vue").read_text()
    assert "toggleShellMenu" in shell
    assert "mobile-nav-backdrop" in shell
    assert "sp-mobile-nav-open" in css
    assert "sp-calendar-grid" in calendar


def test_branding_ui_supports_light_dark_pwa_favicon_and_native_login() -> None:
    web = _web_root()
    source = (web / "src" / "TenantVisualPageBuilder.vue").read_text()
    assert "Logo claro" in source
    assert "Logo escuro" in source
    assert "Ícone PWA" in source
    assert "Favicon" in source
    assert "Login não usa template HTML" in source


def test_control_plane_developer_kit_is_embedded_with_master_standard_and_example() -> None:
    kit = API / "resources" / "avb-template-kit"
    expected = {
        "ARGWS_Visual_Builder_2.4.0_TEMPLATE_AI_STANDARD.md",
        "TEMPLATE_RUNTIME_SDK_V1.md",
        "EXPERIENCE_CONTRACT_V2.md",
        "BINDINGS_V1.md",
        "THEME_TOKENS_V1.md",
        "MIGRATION_V1_TO_V2.md",
        "ARGWS_Experience_Template_v2_EXEMPLO-ENRIQUECIDO.zip",
        "argws-visual-builder-2.4.0.tgz",
    }
    assert kit.is_dir()
    assert expected.issubset({path.name for path in kit.iterdir() if path.is_file()})
    example = ExperienceContractService.parse_archive(
        (kit / "ARGWS_Experience_Template_v2_EXEMPLO-ENRIQUECIDO.zip").read_bytes()
    )
    assert example.package_key == "premium-client-quickstart"
    assert example.landing_html
    assert example.booking_html
    assert len(example.assets) >= 3


def test_control_plane_exposes_sdk_template_studio_when_web_sources_are_available() -> None:
    web = _web_root()
    admin = web.parent / "admin"
    if not admin.is_dir():
        pytest.skip("Fontes Admin não fazem parte desta árvore de execução.")
    source = (admin / "src" / "AdminControlPlane.vue").read_text()
    routes = (API / "app" / "api" / "v1" / "routes" / "platform_templates.py").read_text()
    assert "SDK & Template Studio" in source
    assert "template-studio" in source
    assert "/platform/templates/developer-kit" in source
    assert '@router.get("/developer-kit")' in routes
    assert '@router.get("/developer-kit/artifacts/{artifact}")' in routes

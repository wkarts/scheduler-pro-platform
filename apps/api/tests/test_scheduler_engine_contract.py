from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_engine_routes_are_real() -> None:
    appointment_service = (ROOT / "app/services/appointment_service.py").read_text(encoding="utf-8")
    assert "APPOINTMENT_SLOT_UNAVAILABLE" in appointment_service
    assert "blocked_periods" in appointment_service
    assert "business_hours" in appointment_service
    assert "notification_jobs" in (ROOT / "app/services/notification_service.py").read_text(encoding="utf-8")


def test_no_web_auto_login() -> None:
    app_vue = (ROOT.parents[1] / "apps/web/src/App.vue").read_text(encoding="utf-8")
    assert "const logged = ref(!location.pathname" not in app_vue
    assert "localStorage.getItem('scheduler_pro_access_token')" in app_vue
    assert "@submit.prevent=\"login\"" in app_vue


def test_cloudpanel_argws_compose_has_admin_bootstrap_and_worker_flags() -> None:
    compose = (ROOT.parents[1] / "deployments/cloudpanel/compose.argws.yaml").read_text(encoding="utf-8")
    assert "python -m app.bootstrap platform-admin" in compose
    assert "--without-mingle" in compose
    assert "127.0.0.1" in compose
    assert "18080" in compose

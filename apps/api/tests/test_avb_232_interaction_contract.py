from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_settings_exposes_compact_and_deferred_page_content_routes() -> None:
    source = (ROOT / "app/api/v1/routes/settings.py").read_text(encoding="utf-8")
    assert '@router.get("/tenant/compact")' in source
    assert '@router.get("/tenant/value/{key}")' in source
    assert "booking_page_template_content" in source
    assert "login_page_template_content" in source


def test_template_application_is_atomic_on_backend() -> None:
    source = (ROOT / "app/api/v1/routes/landing_pages.py").read_text(encoding="utf-8")
    assert '@router.post("/template-families/{template_key}/{surface}/apply")' in source
    assert 'normalized == "LANDING"' in source
    assert 'prefix = "booking" if normalized == "BOOKING" else "login"' in source

from app.services.landing_service import LandingPageService


def test_landing_custom_html_sanitizes_script():
    service = LandingPageService(session=None)  # type: ignore[arg-type]
    content = {"version": 1, "sections": [{"type": "custom_html", "html": "<script>alert(1)</script><h1>Ok</h1>"}]}
    sanitized = service.sanitize(content)
    assert "<script" not in sanitized["sections"][0]["html"]
    assert "Ok" in sanitized["sections"][0]["html"]

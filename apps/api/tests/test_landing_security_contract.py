from app.services.landing_service import LandingPageService


def test_editor_sanitizes_scripts_event_handlers_and_javascript_urls() -> None:
    service = LandingPageService(session=None)  # type: ignore[arg-type]
    clean = service.sanitize(
        {
            "version": 2,
            "blocks": [
                {
                    "id": "hero-1",
                    "type": "hero",
                    "props": {
                        "title": "<script>alert(1)</script>Minha página",
                        "onClick": "alert(1)",
                        "url": "javascript:alert(1)",
                        "custom_html": '<div onclick="bad()"><strong>Seguro</strong><script>bad()</script></div>',
                    },
                    "style": {},
                }
            ],
        }
    )
    props = clean["blocks"][0]["props"]
    assert "script" not in props["title"].lower()
    assert "onClick" not in props
    assert props["url"] == ""
    assert "onclick" not in props["custom_html"].lower()
    assert "<script" not in props["custom_html"].lower()
    assert "<strong>Seguro</strong>" in props["custom_html"]


def test_safe_relative_and_https_urls_are_preserved() -> None:
    service = LandingPageService(session=None)  # type: ignore[arg-type]
    clean = service.sanitize(
        {
            "version": 2,
            "seo": {"canonical_url": "https://agenda.example.com/agendar"},
            "blocks": [
                {
                    "id": "image-1",
                    "type": "image",
                    "props": {"image": "/media/photo.webp", "alt": "Foto"},
                    "style": {},
                }
            ],
        }
    )
    assert clean["seo"]["canonical_url"] == "https://agenda.example.com/agendar"
    assert clean["blocks"][0]["props"]["image"] == "/media/photo.webp"

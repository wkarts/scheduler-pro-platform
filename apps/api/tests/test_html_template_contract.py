from app.services.html_template_contract import HtmlTemplateContract
from app.services.landing_service import LandingPageService


LANDING_HTML = """<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="scheduler-pro-template" content="modelo-teste">
<meta name="scheduler-pro-content-version" content="2">
<meta name="scheduler-pro-surface" content="landing">
<style>.top{position:sticky;top:0}@media(max-width:640px){.top{position:static}}</style>
</head><body><main>Landing</main></body></html>"""

BOOKING_HTML = """<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="scheduler-pro-template" content="modelo-teste">
<meta name="scheduler-pro-content-version" content="2">
<meta name="scheduler-pro-surface" content="public-booking">
<style>@media(max-width:640px){main{padding:10px}}</style>
</head><body><main data-scheduler-pro-booking>Agenda</main>
<script>fetch(window.location.origin + '/api/v1/public/booking')</script>
</body></html>"""


def test_html_landing_is_first_class_and_css_top_is_not_parent_access() -> None:
    report = HtmlTemplateContract.validate_html(
        LANDING_HTML,
        expected_surface="LANDING",
    )
    assert report["valid"] is True
    assert report["template_key"] == "modelo-teste"
    assert not any(
        issue["code"] == "HTML_PARENT_ACCESS_FORBIDDEN"
        for issue in report["errors"]
    )


def test_html_booking_contract_accepts_public_booking_api() -> None:
    report = HtmlTemplateContract.validate_html(
        BOOKING_HTML,
        expected_surface="BOOKING",
    )
    assert report["valid"] is True
    assert report["surface"] == "BOOKING"


def test_html_pair_requires_same_template_key() -> None:
    valid = HtmlTemplateContract.validate_pair(
        landing_html=LANDING_HTML,
        booking_html=BOOKING_HTML,
    )
    assert valid["valid"] is True

    invalid = HtmlTemplateContract.validate_pair(
        landing_html=LANDING_HTML,
        booking_html=BOOKING_HTML.replace(
            'content="modelo-teste"',
            'content="outro-modelo"',
            1,
        ),
    )
    assert invalid["valid"] is False
    assert any(
        issue["code"] == "HTML_TEMPLATE_PAIR_KEY_MISMATCH"
        for issue in invalid["errors"]
    )


def test_external_script_is_rejected() -> None:
    html = LANDING_HTML.replace(
        "</body>",
        '<script src="https://example.com/app.js"></script></body>',
    )
    report = HtmlTemplateContract.validate_html(html, expected_surface="LANDING")
    assert report["valid"] is False
    assert any(
        issue["code"] == "HTML_EXTERNAL_SCRIPT_FORBIDDEN"
        for issue in report["errors"]
    )


def test_landing_service_preserves_validated_html_document() -> None:
    service = LandingPageService(session=None)  # type: ignore[arg-type]
    content = HtmlTemplateContract.wrapper(
        LANDING_HTML,
        expected_surface="LANDING",
    )
    sanitized = service.sanitize(content)
    assert sanitized["render_mode"] == "HTML"
    assert sanitized["html_document"] == LANDING_HTML
    assert "@media(max-width:640px)" in sanitized["html_document"]

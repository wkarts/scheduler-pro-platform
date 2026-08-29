from pathlib import Path


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "web").is_dir():
            return parent
    return None


def _read(path: str) -> str:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")
    return (root / path).read_text(encoding="utf-8")


def test_mobile_checkin_keeps_agenda_operator_action_visible() -> None:
    center = _read("apps/web/src/TenantCheckInCenter.vue")
    css = _read("apps/web/src/tenant-checkin-mobile-operator.css")
    app = _read("apps/web/src/App.vue")

    assert "openAgendaOperator({tab:'manage'})" in center
    assert ".sp-checkin-head-actions > button:not(.close)" in css
    assert "display: grid !important" in css
    assert "@media (max-width: 700px)" in css
    assert "tenant-checkin-mobile-operator.css" in app

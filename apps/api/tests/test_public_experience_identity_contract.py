from pathlib import Path


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "web").is_dir() and (parent / "packages" / "visual-builder").is_dir():
            return parent
    return None


def _read(path: str) -> str:
    root = _root()
    if root is None:
        import pytest
        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")
    return (root / path).read_text(encoding="utf-8")


def test_public_experience_preserves_package_identity() -> None:
    source = _read("apps/web/src/PublicSitePage.vue")
    assert "'business.logo':brand.assets.logo_url" not in source
    assert "'brand.logo':brand.assets.logo_url" not in source
    assert "'business.name':brand.app.public_name" not in source
    assert "result.page.template_key==='scheduler-pro-padrao-generico'" not in source
    assert "return result.version.theme||{}" in source


def test_theme_tokens_support_reactive_objects_without_structured_clone() -> None:
    source = _read("packages/visual-builder/src/theme-tokens.js")
    assert "structuredClone" not in source
    assert "function clonePlain" in source


def test_public_frame_has_desktop_reveal_recovery() -> None:
    source = _read("apps/web/src/HtmlTemplateFrame.vue")
    assert "function ensureRevealVisibility()" in source
    assert "classList.add('visible')" in source
    assert "classList.add('is-visible')" in source

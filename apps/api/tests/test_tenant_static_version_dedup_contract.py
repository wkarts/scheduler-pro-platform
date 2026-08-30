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


def test_tenant_removes_static_sidebar_versions_and_keeps_runtime_version() -> None:
    app = _read("apps/web/src/App.vue")
    css = _read("apps/web/src/tenant-version-dedup.css")
    guard = _read("apps/web/src/tenantStaticVersionGuard.ts")
    runtime = _read("apps/web/src/TenantRuntimeVersion.vue")

    assert "tenant-version-dedup.css" in app
    assert "installTenantStaticVersionGuard" in app
    assert ".tenant-console .brand > div > small" in css
    assert ".tenant-console .sidebar-footer > .version-info" in css
    assert "display: none !important" in css
    assert "STATIC_VERSION_SELECTORS" in guard
    assert ".tenant-console .brand > div > small" in guard
    assert ".tenant-console .sidebar-footer > .version-info" in guard
    assert "element.remove()" in guard
    assert "MutationObserver" in guard
    assert "fetch('/api/v1/version'" in runtime
    assert "release_tag" in runtime
    assert "build_sha" in runtime
    assert "tenant-runtime-version" in runtime


def test_control_plane_is_not_part_of_tenant_version_dedup() -> None:
    css = _read("apps/web/src/tenant-version-dedup.css")
    guard = _read("apps/web/src/tenantStaticVersionGuard.ts")
    assert ".tenant-console" in css
    assert ".tenant-console" in guard
    assert ".admin" not in css
    assert ".admin" not in guard
    assert "control-plane" not in css.lower()
    assert "control-plane" not in guard.lower()

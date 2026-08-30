from pathlib import Path

import json

import pytest


CANONICAL_VERSION = "1.0.0"


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (
            (parent / "VERSION").is_file()
            and (parent / "apps" / "web").is_dir()
            and (parent / ".github" / "workflows").is_dir()
        ):
            return parent
    return None


def _read(path: str) -> str:
    root = _root()
    if root is None:
        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")
    return (root / path).read_text(encoding="utf-8")


def _package_version(path: str) -> str:
    return str(json.loads(_read(path))["version"])


def test_scheduler_pro_source_metadata_starts_at_1_0_0() -> None:
    assert _read("VERSION").strip() == CANONICAL_VERSION

    scheduler_packages = (
        "package.json",
        "apps/web/package.json",
        "apps/admin/package.json",
        "apps/desktop/package.json",
        "apps/admin-desktop/package.json",
        "apps/mobile/package.json",
        "apps/admin-mobile/package.json",
        "packages/api-client/package.json",
        "packages/types/package.json",
    )
    for path in scheduler_packages:
        assert _package_version(path) == CANONICAL_VERSION, path

    # ARGWS Visual Builder possui uma linha de produto independente.
    assert _package_version("packages/visual-builder/package.json") == "2.4.0"


def test_native_metadata_is_aligned_without_enabling_native_artifact_flows() -> None:
    for path in (
        "apps/desktop/src-tauri/tauri.conf.json",
        "apps/admin-desktop/src-tauri/tauri.conf.json",
        "apps/mobile/src-tauri/tauri.conf.json",
        "apps/admin-mobile/src-tauri/tauri.conf.json",
    ):
        assert str(json.loads(_read(path))["version"]) == CANONICAL_VERSION, path

    for path in (
        "apps/desktop/src-tauri/Cargo.toml",
        "apps/admin-desktop/src-tauri/Cargo.toml",
        "apps/mobile/src-tauri/Cargo.toml",
        "apps/admin-mobile/src-tauri/Cargo.toml",
    ):
        cargo = _read(path)
        assert 'version = "1.0.0"' in cargo, path
        assert "0.1.0-alpha" not in cargo, path

    release = _read(".github/workflows/release.yml")
    assert "if: ${{ false }}" in release
    assert "Android debug installable" in release
    assert "iOS unsigned IPA" in release


def test_canonical_release_uses_stable_semver_instead_of_alpha_counter() -> None:
    canonical = _read(".github/workflows/canonical-merge-release.yml")
    assert "v0.1.0-alpha" not in canonical
    assert "semver:minor" in canonical
    assert "semver:major" in canonical
    assert 'grep -E \'^[0-9]+\\.[0-9]+\\.[0-9]+$\'' in canonical
    assert '-f image_tag="$TAG"' in canonical

    release = _read(".github/workflows/release.yml")
    assert "v0.1.0-alpha" not in release
    assert "SCHEDULER_PRO_VERSION" in release
    assert '"recommended_value": "${SCHEDULER_PRO_VERSION}"' in release


def test_ghcr_publishes_version_latest_and_immutable_sha() -> None:
    images = _read(".github/workflows/images.yml")
    assert "APP_VERSION=${{ needs.version.outputs.version }}" in images
    assert "APP_RELEASE_TAG=${{ needs.version.outputs.version }}" in images
    assert 'version_ref="${REGISTRY_PREFIX}/${image}:${RELEASE_VERSION}"' in images
    assert 'latest_ref="${REGISTRY_PREFIX}/${image}:latest"' in images
    assert 'source_ref="${REGISTRY_PREFIX}/${image}:${GITHUB_SHA}"' in images
    assert "A tag latest somente foi movida depois" in images

    compose = _read("deployments/cloudpanel/compose.argws.yaml")
    assert "${APP_IMAGE_TAG:-latest}" in compose


def test_api_and_worker_fallback_build_metadata_is_canonical() -> None:
    for path in (
        "infrastructure/docker/api/Dockerfile",
        "infrastructure/docker/worker/Dockerfile",
    ):
        dockerfile = _read(path)
        assert "ARG APP_VERSION=1.0.0" in dockerfile, path
        assert "ARG APP_BUILD_SHA=" in dockerfile, path
        assert "0.1.0-alpha" not in dockerfile, path

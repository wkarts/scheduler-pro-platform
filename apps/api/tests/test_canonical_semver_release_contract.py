from pathlib import Path

import json
import re

import pytest


SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


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


def _package(path: str) -> dict:
    return dict(json.loads(_read(path)))


def _package_version(path: str) -> str:
    return str(_package(path)["version"])


def _canonical_version() -> str:
    version = _read("VERSION").strip()
    assert SEMVER_RE.fullmatch(version), version
    return version


def test_scheduler_pro_source_metadata_follows_canonical_version() -> None:
    canonical_version = _canonical_version()

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
        assert _package_version(path) == canonical_version, path

    # ARGWS Visual Builder possui linha de produto independente e não é
    # sincronizado pelo versionador canônico do Scheduler Pro.
    visual_builder = _package("packages/visual-builder/package.json")
    assert visual_builder["name"] == "@argws/visual-builder"
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-.][0-9A-Za-z.-]+)?", str(visual_builder["version"]))


def test_native_metadata_is_aligned_without_enabling_native_artifact_flows() -> None:
    canonical_version = _canonical_version()

    for path in (
        "apps/desktop/src-tauri/tauri.conf.json",
        "apps/admin-desktop/src-tauri/tauri.conf.json",
        "apps/mobile/src-tauri/tauri.conf.json",
        "apps/admin-mobile/src-tauri/tauri.conf.json",
    ):
        assert str(json.loads(_read(path))["version"]) == canonical_version, path

    for path in (
        "apps/desktop/src-tauri/Cargo.toml",
        "apps/admin-desktop/src-tauri/Cargo.toml",
        "apps/mobile/src-tauri/Cargo.toml",
        "apps/admin-mobile/src-tauri/Cargo.toml",
    ):
        cargo = _read(path)
        assert f'version = "{canonical_version}"' in cargo, path
        assert "0.1.0-alpha" not in cargo, path

    release = _read(".github/workflows/release.yml")
    assert "if: ${{ false }}" in release
    assert "Android debug installable" in release
    assert "iOS unsigned IPA" in release


def test_canonical_release_uses_stable_semver_instead_of_alpha_counter() -> None:
    canonical = _read(".github/workflows/canonical-merge-release.yml")
    assert "v0.1.0-alpha" not in canonical
    assert "version:patch" in canonical
    assert "version:minor" in canonical
    assert "version:major" in canonical
    assert "semver:minor" in canonical
    assert "semver:major" in canonical
    assert "BREAKING CHANGE" in canonical
    assert '-f image_tag="$TAG"' in canonical

    release = _read(".github/workflows/release.yml")
    assert "v0.1.0-alpha" not in release
    assert "SCHEDULER_PRO_VERSION" in release
    assert '"recommended_value": "${SCHEDULER_PRO_VERSION}"' in release


def test_ghcr_publishes_hierarchical_tags_latest_and_immutable_sha() -> None:
    images = _read(".github/workflows/images.yml")
    assert "APP_VERSION=${{ needs.version.outputs.version }}" in images
    assert "APP_RELEASE_TAG=${{ needs.version.outputs.version }}" in images
    assert 'version_ref="${REGISTRY_PREFIX}/${image}:${RELEASE_VERSION}"' in images
    assert 'for alias in "$MINOR_TAG" "$MAJOR_TAG"' in images
    assert 'latest_ref="${REGISTRY_PREFIX}/${image}:latest"' in images
    assert 'source_ref="${REGISTRY_PREFIX}/${image}:${SOURCE_SHA}"' in images
    assert "source_sha: ${{ steps.resolve.outputs.source_sha }}" in images
    assert "platforms: linux/amd64" in images
    assert "linux/arm64" not in images
    assert "setup-qemu" not in images

    # A promoção da SemVer completa precede os aliases móveis.
    full_version = images.index('version_ref="${REGISTRY_PREFIX}/${image}:${RELEASE_VERSION}"')
    minor_major = images.index('for alias in "$MINOR_TAG" "$MAJOR_TAG"')
    latest = images.index('latest_ref="${REGISTRY_PREFIX}/${image}:latest"')
    assert full_version < minor_major < latest

    compose = _read("deployments/cloudpanel/compose.argws.yaml")
    assert "${APP_IMAGE_TAG:-latest}" in compose


def test_api_and_worker_fallback_build_metadata_matches_version_file() -> None:
    canonical_version = _canonical_version()
    for path in (
        "infrastructure/docker/api/Dockerfile",
        "infrastructure/docker/worker/Dockerfile",
    ):
        dockerfile = _read(path)
        assert f"ARG APP_VERSION={canonical_version}" in dockerfile, path
        assert "ARG APP_BUILD_SHA=" in dockerfile, path
        assert "0.1.0-alpha" not in dockerfile, path

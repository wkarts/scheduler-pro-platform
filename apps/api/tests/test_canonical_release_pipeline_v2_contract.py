from __future__ import annotations

import json
from pathlib import Path

import pytest


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "VERSION").is_file() and (parent / ".github" / "workflows").is_dir():
            return parent
    return None


def _read(relative: str) -> str:
    root = _root()
    if root is None:
        pytest.skip("Fontes completas do monorepo não estão presentes nesta imagem.")
    return (root / relative).read_text(encoding="utf-8")


def test_canonical_bump_supports_labels_and_conventional_titles() -> None:
    workflow = _read(".github/workflows/canonical-merge-release.yml")
    for label in ("version:patch", "version:minor", "version:major"):
        assert label in workflow
    assert "semver:major" in workflow
    assert "semver:minor" in workflow
    assert "semver:patch" in workflow
    assert "BREAKING CHANGE" in workflow
    assert "^feat" in workflow
    assert 'bump="patch"' in workflow


def test_version_is_persisted_before_canonical_publication() -> None:
    workflow = _read(".github/workflows/canonical-merge-release.yml")
    assert "scripts/release/sync-product-version.py" in workflow
    assert 'git commit -m "chore(release): ${tag}"' in workflow
    assert "git push origin HEAD:main" in workflow
    assert "Scheduler-Pro-Source-Merge" in workflow
    assert "RELEASE-MANIFEST.json" in workflow


def test_images_finish_before_tag_and_release_are_created() -> None:
    workflow = _read(".github/workflows/canonical-merge-release.yml")
    images = workflow.index("Build and publish canonical GHCR images first")
    tag = workflow.index("Create immutable canonical Git tag after image publication")
    release = workflow.index("Publish GitHub Release only after GHCR succeeds")
    assert images < tag < release
    assert "gh run watch" in workflow
    assert "--exit-status" in workflow


def test_ghcr_has_full_minor_major_latest_sha_and_multiarch() -> None:
    workflow = _read(".github/workflows/images.yml")
    assert "linux/amd64,linux/arm64" in workflow
    assert "minor_tag" in workflow
    assert "major_tag" in workflow
    assert 'for alias in "$MINOR_TAG" "$MAJOR_TAG" latest' in workflow
    assert "SOURCE_SHA" in workflow
    assert "docker buildx imagetools inspect" in workflow
    assert "linux/amd64" in workflow
    assert "linux/arm64" in workflow


def test_develop_publishes_homolog_and_sha_without_release() -> None:
    workflow = _read(".github/workflows/homolog-images.yml")
    assert "branches: [develop]" in workflow
    assert "linux/amd64,linux/arm64" in workflow
    assert ":homolog" in workflow
    assert "${{ github.sha }}" in workflow
    assert "gh release" not in workflow


def test_version_sync_excludes_visual_builder_and_covers_product_metadata() -> None:
    script = _read("scripts/release/sync-product-version.py")
    assert 'packages/visual-builder/package.json' in script
    assert "JSON_VERSION_FILES" in script
    assert "TAURI_FILES" in script
    assert "CARGO_FILES" in script
    assert "DOCKERFILES" in script
    assert "sync_health_default" in script
    assert "RELEASE-MANIFEST.json" in script
    version_list = script.split("JSON_VERSION_FILES", 1)[1].split("]", 1)[0]
    assert '"packages/visual-builder/package.json",' not in version_list


def test_persisted_release_manifest_is_well_formed() -> None:
    root = _root()
    if root is None:
        pytest.skip("Fontes completas do monorepo não estão presentes nesta imagem.")
    payload = json.loads((root / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "scheduler-pro-release-manifest/v1"
    assert payload["product"] == "Scheduler Pro"
    assert payload["version"] == (root / "VERSION").read_text(encoding="utf-8").strip()
    assert payload["visual_builder"]["package"] == "@argws/visual-builder"


def test_native_apk_and_ipa_release_jobs_remain_paused() -> None:
    release = _read(".github/workflows/release.yml")
    assert "android-debug-apks:" in release
    assert "ios-unsigned-ipas:" in release
    assert release.count("if: ${{ false }}") >= 2

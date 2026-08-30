from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_visual_builder_keeps_independent_version_line() -> None:
    package = _read("packages/visual-builder/package.json")
    scheduler_version = _read("VERSION").strip()
    assert '"name": "@argws/visual-builder"' in package
    assert '"version": "2.4.0"' in package
    assert scheduler_version == "1.0.0"
    assert '"version": "1.0.0"' not in package


def test_every_successful_release_can_package_visual_builder_separately() -> None:
    workflow = _read(".github/workflows/visual-builder-package.yml")
    assert "workflow_run:" in workflow
    assert "workflows: ['Release']" in workflow
    assert "workflow_dispatch:" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "@argws/visual-builder" in workflow
    assert "npm --workspace packages/visual-builder run check" in workflow
    assert "npm --workspace packages/visual-builder test" in workflow
    assert "npm pack --workspace packages/visual-builder" in workflow
    assert "argws-visual-builder-${ARGWS_VISUAL_BUILDER_VERSION}-source.tar.gz" in workflow
    assert "argws-visual-builder-${ARGWS_VISUAL_BUILDER_VERSION}-manifest.json" in workflow
    assert "argws-visual-builder-${ARGWS_VISUAL_BUILDER_VERSION}-SHA256SUMS.txt" in workflow
    assert "gh release upload \"$RELEASE_TAG\" artifacts/* --clobber" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "argws-visual-builder-${{ steps.visual_builder.outputs.version }}-scheduler-" in workflow


def test_visual_builder_release_does_not_reactivate_native_mobile_builds() -> None:
    release = _read(".github/workflows/release.yml")
    assert "android-debug-apks:" in release
    assert "ios-unsigned-ipas:" in release
    assert release.count("if: ${{ false }}") >= 2


def test_initial_1_0_0_backfill_is_guarded_by_source_identity() -> None:
    workflow = _read(".github/workflows/visual-builder-package.yml")
    assert "Backfill canonical 1.0.0 when Visual Builder source is identical" in workflow
    assert "git diff --quiet '1.0.0^{commit}' HEAD -- packages/visual-builder" in workflow
    assert "backfill automático recusado por segurança" in workflow
    assert "gh release upload 1.0.0 backfill/* --clobber" in workflow

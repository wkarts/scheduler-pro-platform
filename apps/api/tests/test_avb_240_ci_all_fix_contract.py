from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path | None:
    for candidate in (API_ROOT, *API_ROOT.parents):
        if (candidate / "apps/api").is_dir() and (candidate / "apps/web").is_dir():
            return candidate
    return None


def test_developer_kit_binaries_are_not_gitignored() -> None:
    repo = _repo_root()
    if repo is None:
        pytest.skip("Monorepo não disponível na imagem isolada da API.")
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (repo / ".dockerignore").read_text(encoding="utf-8")
    for source in (gitignore, dockerignore):
        assert "!apps/api/resources/avb-template-kit/*.zip" in source
        assert "!apps/api/resources/avb-template-kit/*.tgz" in source


def test_web_pwa_contract_matches_no_cache_registration_and_revalidation_handler() -> None:
    repo = _repo_root()
    if repo is None:
        pytest.skip("Monorepo não disponível na imagem isolada da API.")
    validator = (repo / "scripts/build/validate-pwa-install.mjs").read_text(encoding="utf-8")
    pwa = (repo / "apps/web/src/pwa.ts").read_text(encoding="utf-8")
    console = (repo / "apps/web/src/TenantConsole.vue").read_text(encoding="utf-8")
    assert "navigator.serviceWorker.register('/sw.js'" in validator
    assert "updateViaCache: 'none'" in validator
    assert "navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })" in pwa
    assert "async function onAppRevalidate()" in console


def test_integration_workflow_does_not_double_run_feature_push_and_pull_request() -> None:
    repo = _repo_root()
    if repo is None:
        pytest.skip("Monorepo não disponível na imagem isolada da API.")
    workflow = (repo / ".github/workflows/integration-tests.yml").read_text(encoding="utf-8")
    assert "branches: [main]" in workflow
    assert "'feat/**'" not in workflow
    assert "'fix/**'" not in workflow
    assert "github.event.pull_request.head.ref || github.ref_name" in workflow

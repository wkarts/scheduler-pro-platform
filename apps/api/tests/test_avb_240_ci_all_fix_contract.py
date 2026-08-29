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


def test_integration_workflow_preserves_canonical_triggers_and_concurrency() -> None:
    repo = _repo_root()
    if repo is None:
        pytest.skip("Monorepo não disponível na imagem isolada da API.")
    workflow = (repo / ".github/workflows/integration-tests.yml").read_text(encoding="utf-8")
    assert "branches: [main, 'fix/**', 'feat/**']" in workflow
    assert "group: integration-${{ github.ref }}" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "docker compose -f deployments/development/docker-compose.yml up --build -d" in workflow

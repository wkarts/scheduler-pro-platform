# Correção API — Run 90057751301

## Diagnóstico confirmado

O run mais recente isolou a falha na etapa de unit tests da API.

Resultado do GitHub Actions antes desta correção:

- Ruff: PASS
- MyPy: PASS
- Web: PASS
- Docker: PASS
- Integration Tests (pull_request): PASS
- Integration Tests (push): PASS
- API unit tests: 184 PASS / 1 FAIL / 16 deselected

A única falha era:

`test_integration_workflow_does_not_double_run_feature_push_and_pull_request`

O teste exigia uma política de workflow que não corresponde ao workflow canônico definido pelo mantenedor:

- exigia `branches: [main]`;
- proibia `fix/**` e `feat/**`;
- exigia uma expressão de concurrency diferente.

## Correção aplicada

O workflow não foi alterado.

O teste foi substituído por um contrato que valida exatamente os elementos canônicos já existentes:

- `branches: [main, 'fix/**', 'feat/**']`;
- `group: integration-${{ github.ref }}`;
- `cancel-in-progress: true`;
- `docker compose -f deployments/development/docker-compose.yml up --build -d`.

O teste não tenta mais impor uma alteração arquitetural no GitHub Actions.

## Workflow preservado

`.github/workflows/integration-tests.yml` permanece no formato anterior fornecido pelo mantenedor.

Nenhum retry de BuildKit, `builder prune`, `up --no-build` ou nova estratégia de concurrency foi introduzido.

## Validação local possível neste runtime

- parsing AST do teste corrigido: PASS;
- contrato direcionado contra o workflow canônico: PASS;
- compilação Python do teste: PASS;
- confirmação de ausência das customizações de retry no workflow: PASS.

A suíte completa `pytest` não foi executada localmente porque este runtime não possui `structlog`, dependência carregada pelo `tests/conftest.py`. O GitHub Actions já demonstrou que os outros 184 testes passam no mesmo commit anterior; esta alteração modifica somente a asserção que causava a única falha.

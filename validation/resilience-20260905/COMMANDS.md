# Comandos das execuções suportadas

Executar da raiz, exceto onde indicado. Os logs registram as execuções neste ambiente.

```bash
(cd apps/api && python -m unittest discover -s tests -p test_resilience_core.py -v)
node --test scripts/tests/auth-fetch.test.cjs
python -m unittest discover -s scripts/tests -p test_operations.py -v
node --test packages/visual-builder/tests/*.test.js
npm --workspace packages/visual-builder run check
node scripts/build/validate-pwa-install.mjs
python -m compileall -q apps/api/app apps/api/tests scripts/operations scripts/tests
sh -n infrastructure/docker/acme/entrypoint.sh
bash -n infrastructure/docker/cloudpanel-agent/entrypoint.sh

# Contratos de fonte preexistentes selecionados; NÃO equivale à suíte inteira.
# O --noconftest foi usado porque esses testes não requerem a aplicação/DB.
(cd apps/api && pytest --noconftest -q $(sed 's#^apps/api/##' ../../validation/resilience-20260905/static-tests-selected.txt))
```

O runner Node de autenticação compila os dois wrappers TS com `--strict`, executa testes com fetch/storage simulados e limpa a saída temporária. Os testes de operações usam subprocessos para o cálculo de budget, mas simulam Docker no teste de backup. O arquivo `compose-and-budget.txt` é uma simulação dos defaults dos modelos YAML, não execução de Docker Compose nem medição do banco.

Para validação integral utilize os workflows existentes e dependências normais do projeto. Não substitua o comando `pytest` completo do CI pela seleção acima. A tentativa local integral parou no import da dependência ausente, conforme log preservado.

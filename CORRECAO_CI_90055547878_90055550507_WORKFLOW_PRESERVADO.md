# Correção CI — runs 90055547878 / 90055550507

## Regra desta rodada

O arquivo `.github/workflows/integration-tests.yml` foi preservado exatamente no formato fornecido pelo mantenedor, correspondente ao workflow estável anterior às tentativas de retry/orquestração adicional.

Nenhuma engenharia nova de retry, `--no-build` ou alteração de concurrency foi introduzida nesta correção.

## Falhas observadas nos logs

### Web

O validador PWA procurava literalmente `navigator.serviceWorker.register('/sw.js')`, mas a implementação 2.4.0 usa `navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })`.

O validador agora verifica separadamente:

- registro de `/sw.js`;
- `updateViaCache: 'none'`.

### Docker / Web build

`TenantConsole.vue` referenciava `onAppRevalidate` em listeners sem implementação no commit que originou o log. A implementação está presente nesta entrega e faz revalidação best-effort da view ativa sem reload artificial.

### API

O run chegou a 176 testes aprovados e 6 falhas de contratos. Foram corrigidos/alinhados:

- Developer Kit/SDK Studio embarcado;
- remoção do teste artificial que obrigava retry no GitHub Actions;
- compatibilidade de branding padrão legado com a nova identidade Scheduler Pro;
- prefixos públicos `landing/` e `experience/`;
- contrato do editor para `ExperiencePageAdapter` e o custom element real `argws-visual-builder`.

### Integration

A suíte agregada falhava durante coleta porque um contrato calculava a raiz usando profundidade fixa de `Path.parents` dentro da imagem `/app`.

O teste agora procura o monorepo de forma portátil e faz skip apenas das verificações Web quando a imagem isolada da API realmente não contém essas fontes. Os contratos de API continuam executáveis dentro de `/app`.

## Workflow preservado

Permanece:

- `pull_request` com os paths originais;
- `push` em `main`, `fix/**`, `feat/**`;
- `concurrency: integration-${{ github.ref }}`;
- `docker compose ... up --build -d`;
- testes individuais;
- suíte integrada em processo único;
- downgrade/re-upgrade de migrations;
- smoke test;
- diagnósticos e cleanup.

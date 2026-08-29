# ARGWS Visual Builder 2.3.2 — correção de interações e performance

## Diagnóstico de produção

O log de 2026-08-28 mostrou a API saudável (`/health/ready` 200) e ausência de erros 5xx durante o incidente. O problema principal estava na camada do Visual Builder.

### 1. Ações do Workspace não eram realmente ligadas ao ShadowRoot

O Workspace usava:

```js
shadowRoot.onclick = ...
```

`ShadowRoot` é um `EventTarget`, porém não deve depender da propriedade `onclick` como mecanismo de binding. O resultado observado em produção foi compatível com isso: tema, importar, fechar, editar, toggles e aplicar template não geravam as chamadas esperadas.

O log confirma que o catálogo `/landing-pages/template-families` era carregado, mas durante os cliques não apareciam `PUT /settings/tenant/...` nem aplicação de template.

Correção: `addEventListener()` real no lifecycle do Custom Element, uma única vez, com `removeEventListener()` no disconnect e resolução do botão por `event.composedPath()`.

### 2. Aplicar template agora possui confirmação interna e operação atômica

Novo fluxo:

1. usuário clica em `Aplicar template`;
2. AVB abre Confirm interno;
3. backend recebe um único `POST /landing-pages/template-families/{key}/{surface}/apply`;
4. backend persiste LANDING, BOOKING ou LOGIN;
5. documento salvo retorna ao editor;
6. editor abre sem recarregar o template anterior.

LANDING é salvo como nova versão draft. BOOKING e LOGIN persistem conteúdo + key + version em uma única transação.

### 3. Importação agora persiste no Scheduler Pro

Anteriormente `_mergeImportedProject()` atualizava somente o Project Workspace em memória, porque `saveProject()` do adapter Scheduler Pro não persiste superfícies públicas.

Agora ZIP/Project Package salva as páginas canônicas LANDING, BOOKING e LOGIN no backend. HTML avulso também substitui/persiste a superfície correspondente quando aplicável.

### 4. Settings de 1,64 MB retirados do bootstrap do tenant

O log mostrou:

```text
GET /api/v1/settings/tenant
200
~1.643.156 bytes
```

O payload continha HTML completo de Booking e Login em `tenant_settings`.

Foi criado:

```text
GET /api/v1/settings/tenant/compact
GET /api/v1/settings/tenant/value/{key}
```

O Tenant Console, Agenda, Booking/Messages e AVB usam o endpoint compacto. O HTML pesado é carregado apenas quando a página correspondente é aberta para edição.

### 5. Landing de 6,5 s corrigida na origem

O log mostrou:

```text
GET /api/v1/landing-pages/home
200
1.526.987 bytes
6.550 ms
```

Além do documento HTML grande, `LandingPageService.versions()` fazia `select(LandingPageVersion)` para até 100 versões. Isso carregava o campo `content` completo de todas as versões mesmo que a resposta usasse somente metadados.

Correções:

- `versions()` seleciona apenas id, versão, label, origem e created_at;
- novo `GET /landing-pages/{slug}/document` retorna apenas o documento efetivo para edição;
- histórico continua carregado separadamente quando solicitado;
- o adapter do AVB usa o endpoint `/document`.

### 6. Tema, fechar e importar

O mesmo fix de eventos resolve os controles do Project Workspace. O editor interno também passou a usar delegação por `composedPath()` e listeners únicos, inclusive para o input de Import.

### 7. PWA

Cache alterado para:

```text
avb-2.3.2-interactionfix-v3
```

para evitar que uma instalação já existente continue utilizando o bundle anterior.

## Validação desta rodada

- ARGWS Visual Builder 2.3.2: 85/85 testes PASS
- `npm run check`: PASS
- 8/8 templates oficiais válidos
- LANDING + BOOKING + LOGIN presentes em todas as famílias
- Python `compileall`: PASS
- Vue/TypeScript: 45 arquivos verificados, 0 falhas sintáticas
- pytest completo local: não executado porque o runtime atual não possui `structlog`; a dependência continua declarada no projeto/CI.

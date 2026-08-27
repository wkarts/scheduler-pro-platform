# ARGWS Visual Builder Universal 2.0.1

Builder visual framework-agnostic para criar Landing Pages, páginas públicas, páginas internas, partes globais de site e experiências web reutilizáveis em qualquer projeto. O núcleo é ES Modules + Web Components e não depende de WordPress, PHP, Python, Vue ou de um backend específico.

## Objetivo

Fornecer a mesma **classe de capacidade** de um page builder profissional: edição visual, layout responsivo, Design System, conteúdo dinâmico, queries, formulários, popups, partes globais de site, componentes reutilizáveis, permissões, extensões e publicação — sem acoplar o produto a um CMS.

A integração oficial prioritária continua sendo o Scheduler Pro, mas o mesmo documento funciona em Laravel/Blade, PHP puro, FastAPI/Jinja2, HTML, Vue, React, Svelte, Node e qualquer backend REST.

## Novidades da 2.0

- schema canônico `argws-visual-builder/v3`, document version `4`;
- 74 widgets nativos, incluindo Nested Tabs/Accordion, Mega Menu, Floating Bar, TOC, Search, Share, Lottie, Hotspot, Flip Box, Slides, Cookie Consent e Commerce provider-driven;
- Dynamic Tags extensíveis com filtros (`upper`, `currency`, `date`, `default`, `join` etc.);
- Data Source Registry + Query Loop assíncrono + cache;
- Form Builder com schema JSON, campos avançados e múltiplas etapas;
- Submission Store genérico (memory/REST) + CSV;
- Interactions por elemento (evento → actions) e atributos HTML seguros;
- Host Services para email, submissions, CAPTCHA, media optimizer, autenticação, pagamentos e serviços do projeto;
- Plugin SDK para registrar widgets, renderers, actions, data sources, tags, filtros e services em um único manifest;
- Asset Library para fontes, ícones e mídia;
- i18n no documento, traduções por nó e locale;
- Role/Capability Policy aplicada às operações sensíveis do editor;
- operações incrementais/revisionadas como base para colaboração;
- Project Package para transportar páginas, SiteKit, ativos, templates e configurações;
- Custom Code controlado; JavaScript somente com `trusted` + opt-in do host;
- snippets de integração para HTML, Blade, PHP, Jinja2, Twig, Vue, React e Svelte;
- Commerce genérico por providers, sem dependência de WooCommerce;
- compilador Scheduler Pro mantém Landing Page V2 e preserva metadata Universal V3.

## Capacidades do editor

- drag-and-drop e touch;
- canvas responsivo;
- containers Flexbox/Grid aninhados;
- Navigator/Layers;
- edição inline;
- undo/redo e histórico remoto;
- Desktop/Tablet/Mobile + breakpoints customizados;
- herança responsiva e visibilidade por breakpoint;
- estados Normal/Hover/Focus/Active;
- cores/fontes/variáveis/classes globais;
- spacing, border, shadow, transform, filter, opacity;
- motion/entrance/sticky;
- templates locais/remotos;
- biblioteca de componentes reutilizáveis;
- SEO/Open Graph/Twitter/JSON-LD;
- auditoria estrutural SEO/acessibilidade;
- import/export JSON;
- export HTML standalone;
- feature flags e adapters de persistência.

## Contrato universal

```json
{
  "schema": "argws-visual-builder/v3",
  "version": 4,
  "surface": "PAGE",
  "settings": {},
  "global_styles": {},
  "design_system": {},
  "seo": {},
  "project": {
    "assets": {"fonts": [], "icons": [], "media": []},
    "custom_code": [],
    "data_requirements": [],
    "i18n": {},
    "permissions": {},
    "collaboration": {"revision": 0},
    "integrations": {}
  },
  "builder": {
    "schema": "argws-visual-builder/v3",
    "root_ids": [],
    "nodes": {}
  }
}
```

## Instalação NPM

```bash
npm install @argws/visual-builder
```

ou pelo TGZ da release:

```bash
npm install ./argws-visual-builder-2.0.1.tgz
```

```js
import '@argws/visual-builder';
import '@argws/visual-builder/styles.css';
```

## Editor

```html
<argws-visual-builder id="builder"></argws-visual-builder>
<script type="module">
  import { RestAdapter } from '@argws/visual-builder';
  const builder = document.getElementById('builder');
  builder.adapter = new RestAdapter({
    loadUrl: '/api/pages/home',
    draftUrl: '/api/pages/home/draft',
    autosaveUrl: '/api/pages/home/autosave',
    publishUrl: '/api/pages/home/publish'
  });
  await builder.load();
</script>
```

## Renderer público

```html
<argws-page-renderer id="page"></argws-page-renderer>
<script type="module">
  import '@argws/visual-builder';
  const response = await fetch('/api/pages/home');
  const payload = await response.json();
  document.getElementById('page').document = payload.data.document;
</script>
```

## Dynamic Tags

```js
import { registerDynamicTag, registerDynamicFilter } from '@argws/visual-builder';

registerDynamicTag('tenant.name', ctx => ctx.tenant.name);
registerDynamicFilter('slug', value => String(value).toLowerCase().replace(/\W+/g, '-'));

// {{ tenant.name | upper }}
// {{ product.price | currency:BRL:pt-BR }}
```

## Data Sources / Query Builder

```js
import { registerDataSource, QueryCache } from '@argws/visual-builder';

registerDataSource('erp.products', async ({ query, runtime }) => {
  const r = await fetch(`/api/products?category=${encodeURIComponent(query.category ?? '')}`,
    { headers: runtime.headers });
  return r.json();
}, { cacheTtl: 30_000 });

const runtime = { queryCache: new QueryCache() };
```

O widget `query_loop` executa o Data Source e renderiza seus filhos com `item`, `index` e `query` no contexto.

## Host Services

```js
import { registerHostService } from '@argws/visual-builder';

registerHostService('mail.send', async ({ payload }) => api.post('/mail', payload));
registerHostService('captcha.verify', async ({ payload }) => verifyCaptcha(payload.token));
registerHostService('payment.create', async ({ payload }) => paymentProvider.create(payload));
```

Actions de formulário podem usar `{ "type": "service", "service": "mail.send" }`.

## Plugin SDK

```js
import { registerBuilderPlugin } from '@argws/visual-builder';

registerBuilderPlugin({
  id: 'argws.erp',
  name: 'ARGWS ERP widgets',
  version: '1.0.0',
  widgets: { /* ... */ },
  renderers: { /* ... */ },
  dataSources: { /* ... */ },
  actions: { /* ... */ },
  dynamicTags: { /* ... */ },
  services: { /* ... */ }
});
```

## Stacks suportadas

Exemplos completos ou snippets estão em `examples/` para:

- HTML/JavaScript puro;
- PHP puro;
- Laravel + Blade;
- Python/FastAPI;
- Jinja2;
- Twig;
- Node/Express;
- Vue;
- React;
- Svelte;
- standalone HTML.

Outras stacks usam o mesmo REST Adapter ou o Web Component diretamente.

## Scheduler Pro

### Política New-Only

- um único editor visual: `ARGWS Visual Builder Universal 2.0`;
- um único renderer visual para páginas em blocos;
- nenhum `TenantPublicPageEditorV2` ativo;
- nenhum `PublicLandingRenderer` como alternativa;
- compatibilidade V1/V2 somente para **migração de dados**.

O instalador incremental está em:

```bash
python integrations/scheduler-pro/install.py /caminho/scheduler-pro-platform
```

O builder Universal V3 compila uma projeção `blocks` compatível com o contrato Landing Page V2 do Scheduler Pro, porém **o runtime usa somente o ARGWS Visual Builder Universal 2.0**.

A integração **New-Only** remove a montagem do editor anterior e do renderer público anterior. Não existe feature flag para alternar de volta ao editor antigo. Documentos V2 existentes são normalizados pelo próprio renderer universal antes da exibição/edição.

## Segurança

- URLs validadas;
- CSS sanitizado;
- HTML em whitelist conservadora;
- JS customizado bloqueado por padrão;
- isolamento entre documento e services do host;
- permissões no editor;
- o backend continua responsável por autorização, validação, rate limit e tenant isolation.

## Testes

```bash
npm run check
npm test
```

A release 2.0.1 mantém a suíte funcional do core/universal e adiciona a integração Scheduler Pro New-Only, além das validações de sintaxe e instalação descritas em `docs/RELEASE_VALIDATION.md`.

## Documentação

- `docs/UNIVERSAL_ARCHITECTURE.md`
- `docs/STACK_INTEGRATIONS.md`
- `docs/CAPABILITY_MATRIX_2.0.md`
- `docs/PLUGIN_SDK.md`
- `docs/DATA_SOURCES.md`
- `docs/SECURITY.md`
- `docs/PERFORMANCE.md`
- `docs/MIGRATION_1_TO_2.md`
- `docs/PROJECT_CHECKPOINT.md`

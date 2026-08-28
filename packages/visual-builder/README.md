# ARGWS Visual Builder Universal 2.3.2


> **2.3.2 — Logo oficial por tema:** atualização incremental e isolada. O Light Mode mantém a logo padrão existente; o Dark Mode usa exatamente a logo dark oficial fornecida, sem recoloração, redesenho ou geração de variantes. Ícones e favicon não são alterados.

## Logo Light/Dark 2.3.2

A seleção de marca usa o mesmo estado de tema já existente no AVB:

```text
theme = light → argws-visual-builder-logo-1600.png
theme = dark  → argws-visual-builder-logo-dark.png
```

A troca ocorre automaticamente no **Visual Editor** e no **Project/Site Workspace**. Em larguras compactas, a interface continua usando o símbolo AVB existente para preservar espaço; esse símbolo não possui variante dark e não foi alterado.

Esta patch **não altera** Project Schema, PageDocument, renderer público, adapters, Plugin SDK, imports, Scheduler Pro ou páginas do usuário. Veja [Dark Logo 2.3.2](docs/DARK_LOGO_2.3.2.md).

> **2.3.1 — Brand Alignment seguro:** alinha Light/Dark Mode à identidade oficial AVB (`#0B1020`, `#1E2435`, `#1AD5E8`, `#2563FF`, `#7A4DFF`, `#E9EEF5`), usa **Space Grotesk somente nos headings da interface do produto** e mantém **Inter** em interface/body. O conteúdo da página editada continua totalmente independente do tema/tipografia do AVB.

## Alinhamento visual 2.3.1

A 2.3.1 é deliberadamente incremental: **não altera schema, documentos, renderer público, adapters, Plugin SDK nem integração Scheduler Pro**. O ajuste fica na camada de Design System do próprio builder.

- Light e Dark Mode usam tokens derivados da identidade oficial;
- o Project/Site Workspace agora também respeita o mesmo tema persistido do editor;
- headings/títulos do AVB usam `Space Grotesk` com fallback seguro para `Inter`/sistema;
- interface, formulários, botões e body do AVB usam `Inter`;
- pesos ficam entre 400 e 700, evitando UI excessivamente pesada;
- ações primárias usam Electric Blue sólido para manter contraste AA; o gradiente oficial continua disponível como token de marca e nos assets;
- cores de texto secundário/muted foram escolhidas para manter contraste AA em Light e Dark;
- o canvas e o documento renderizado **não herdam** `Space Grotesk` nem o tema do editor;
- nenhuma fonte externa é obrigatória: se o host não fornecer Space Grotesk, o fallback mantém legibilidade sem quebrar a aplicação.

Veja [Brand Alignment 2.3.1](docs/BRAND_ALIGNMENT_2.3.1.md).

> **2.3 corrige o modelo de páginas:** o produto agora possui um Project/Site Workspace universal e um Visual Editor dentro da mesma SPA. HTML completo é uma página `mode=HTML`, nunca um widget dentro de outra página.

## Arquitetura 2.3

```text
ARGWS Visual Builder
├── Projeto / Site
│   ├── Páginas
│   ├── Templates
│   ├── Componentes
│   ├── Popups
│   └── Assets / Site Kit
└── Editor Visual
    └── documento selecionado
```

O mesmo `<argws-visual-builder-app>` funciona em Scheduler Pro, Laravel/Blade, PHP, FastAPI/Jinja, Vue, React, Svelte, Node ou qualquer host REST. O projeto hospedeiro fornece somente um adapter.

### Scheduler Pro

Um `scheduler-pro-template-package/v1` com `landing.html` e `agendamento.html` vira **duas páginas independentes** do mesmo projeto:

```text
Landing Page           /pagina   LANDING  HTML
Página de Agendamento  /agendar  BOOKING  HTML
```

A 2.3 migra automaticamente documentos 2.1/2.2 que armazenavam um HTML completo como único `html_surface`.

Veja [Project/Site Workspace 2.3](docs/PROJECT_SITE_WORKSPACE_2.3.md).

---

Builder visual framework-agnostic para criar Landing Pages, páginas públicas, páginas internas, partes globais de site e experiências web reutilizáveis em qualquer projeto. O núcleo é ES Modules + Web Components e não depende de WordPress, PHP, Python, Vue ou de um backend específico.

## Objetivo

Fornecer a mesma **classe de capacidade** de um page builder profissional: edição visual, layout responsivo, Design System, conteúdo dinâmico, queries, formulários, popups, partes globais de site, componentes reutilizáveis, permissões, extensões e publicação — sem acoplar o produto a um CMS.

A integração oficial prioritária continua sendo o Scheduler Pro, mas o mesmo documento funciona em Laravel/Blade, PHP puro, FastAPI/Jinja2, HTML, Vue, React, Svelte, Node e qualquer backend REST.

## Novidades da 2.2

A 2.2 é uma release de refinamento estrutural do editor baseada em uso real no Scheduler Pro:

- **guias laterais persistentes**: Elementos/Camadas/Modelos/Biblioteca e Conteúdo/Estilo/Avançado/Histórico não encolhem nem desaparecem quando o conteúdo do painel cresce;
- cada sidebar possui **scroll independente**, sem empurrar o cabeçalho de abas para fora da tela;
- **toolbar redesenhada**: ações compactas por ícone, com `title`/`aria-label` como hint, reduzindo drasticamente o espaço horizontal;
- Desktop/Tablet/Mobile agora usam apenas ícones e tooltip;
- botões **Elementos** e **Propriedades** funcionam em desktop e em telas pequenas;
- **Configurações da página** força o Inspector para Conteúdo e posiciona o painel no topo;
- **Auditar** abre diretamente a área Avançado com o resultado e score da auditoria;
- ações secundárias entram em um menu `…` em telas menores, enquanto Publicar/Recuperação/Fechar permanecem acessíveis;
- importação de `scheduler-pro-template-package/v1` continua integral e a superfície HTML importada agora **expande a altura no editor**, eliminando o iframe visualmente cortado em ~760 px;
- sandbox de importação no editor permite somente `allow-same-origin` + forms para medição de altura, sem habilitar scripts;
- templates que escondem seções com `reveal`/scroll animation ficam totalmente visíveis no canvas de edição; a regra é apenas de preview e não modifica o HTML original;
- nova **identidade visual AVB/ARGWS Visual Builder**, usando o símbolo e wordmark oficiais fornecidos, com paleta cyan → blue → violet;
- tema claro/escuro, tipografia leve e scrollbars discretas foram recalibrados para a nova identidade;
- instalador Scheduler Pro passa a copiar também os assets de branding do pacote;
- runtime continua New-Only, sem editor anterior.

### Base universal herdada da 2.0

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
- adapters de persistência e extensões por host.

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
npm install ./argws-visual-builder-2.3.2.tgz
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
    baseUrl: '/api/pages',
    slug: 'home'
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

- um único editor visual: `ARGWS Visual Builder Universal 2.3`;
- um único renderer visual para páginas em blocos;
- nenhum `TenantPublicPageEditorV2` ativo;
- nenhum `PublicLandingRenderer` como alternativa;
- compatibilidade V1/V2 somente para **migração de dados**.

O instalador incremental está em:

```bash
python integrations/scheduler-pro/install.py /caminho/scheduler-pro-platform
```

O builder Universal V3 compila uma projeção `blocks` compatível com o contrato Landing Page V2 do Scheduler Pro, porém **o runtime usa somente o ARGWS Visual Builder Universal 2.3**.

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

A release 2.3.2 preserva toda a validação funcional da 2.3.1 e acrescenta testes específicos da seleção automática da logo Light/Dark, distribuição do asset dark oficial e preservação dos ícones. Veja `docs/RELEASE_VALIDATION.md`.

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
- `docs/SCHEDULER_PRO_TEMPLATE_PACKAGES.md`
- `docs/TEMPLATE_PACKAGE_VALIDATION.md`
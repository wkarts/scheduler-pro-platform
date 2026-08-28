# Changelog

## 2.3.2 — Logo oficial por tema (Light/Dark)

- integração isolada da logo dark oficial fornecida, sem gerar ou redesenhar nenhum asset;
- Light Mode continua usando a logo padrão existente `argws-visual-builder-logo-1600.png`;
- Dark Mode usa exclusivamente `argws-visual-builder-logo-dark.png`, em que o nome ARGWS aparece branco conforme o arquivo fornecido;
- troca automática da logo acompanha o tema ativo do Editor e do Project/Site Workspace;
- a mesma regra é compartilhada pelos pontos de branding do núcleo, sem duplicar o sistema de temas;
- em layouts compactos o AVB continua usando o símbolo existente, sem criar ícones dark;
- favicon, ícones de menu, SVGs funcionais e demais assets permanecem inalterados;
- schema, documentos, renderer, adapters, Plugin SDK e integração Scheduler Pro permanecem compatíveis com 2.3.1;
- alteração restrita à camada de branding/versionamento.

### Integração Scheduler Pro 2.3.2

- corrige página HTML completa sendo sobrescrita pelo estado “Página vazia”;
- Project/Site usa carregamento progressivo e documentos lazy;
- templates oficiais são aplicados e salvos antes da abertura do editor;
- LANDING, BOOKING e LOGIN permanecem páginas independentes;
- regressões de save/publicação cobertas pela suíte do pacote.

## 2.3.1 — Brand Alignment seguro e Light/Dark consistente

- paleta oficial AVB consolidada: Deep Navy `#0B1020`, Charcoal `#1E2435`, Cyan `#1AD5E8`, Electric Blue `#2563FF`, Violet `#7A4DFF` e Light Gray `#E9EEF5`;
- headings/títulos do produto passam a usar `Space Grotesk` com fallback seguro para `Inter` e sistema;
- interface, formulários, botões e corpo permanecem em `Inter`;
- Project/Site Workspace ganha Light/Dark Mode sincronizado e persistente com o Editor;
- pesos tipográficos limitados a 400–700 para evitar aparência excessivamente pesada;
- cores `muted`/secundárias recalibradas para contraste WCAG AA em Light e Dark;
- ações primárias usam Electric Blue sólido para garantir texto branco legível; o gradiente oficial permanece como token/elemento de branding;
- o documento/canvas editado não herda Space Grotesk nem o tema do AVB;
- nenhuma fonte externa obrigatória ou CDN foi adicionada;
- schema, Project/Site Workspace, PageDocument, renderer, adapters e integrações permanecem compatíveis com 2.3.0;
- suíte ampliada para 60 testes automatizados, incluindo branding, isolamento tipográfico e contraste Light/Dark.

## 2.3.0 — Project / Site Workspace Universal e páginas de primeira classe

- novo schema `argws-visual-builder-project/v2`;
- novo Web Component `<argws-visual-builder-app>` com Project/Site Workspace + Visual Editor no mesmo produto;
- páginas passam a ser documentos de primeira classe com rota, surface, kind, status e documento próprio;
- novo `mode=HTML` no `PageDocument`: HTML completo deixa de ser widget `html_surface`;
- migração automática de documentos legados cujo único nó era `html_surface`;
- `importSchedulerProTemplateFamily()` importa `landing.html` e `agendamento.html` como duas páginas independentes;
- `SchedulerProProjectAdapter` mapeia LANDING e BOOKING sem criar uma variante do editor;
- `MemoryProjectAdapter`, `RestProjectAdapter` e `ProjectPageAdapter` para qualquer backend;
- integração Scheduler Pro passa a abrir o Project Workspace e chama o mesmo editor universal;
- ZIP real Barber Shop Neo validado com LANDING 3,1 MB + BOOKING 1,6 MB, zero nós `html_surface`;
- suíte ampliada para 53 testes automatizados.

## 2.2.0 — Refinamento de Interface, Toolbar Minimalista e Branding AVB

- corrigida a causa estrutural do desaparecimento das abas laterais: `tabs` e `inspector-head` agora são itens flex não redutíveis;
- `panel-scroll` passa a ocupar somente a área restante e rolar de forma independente;
- toolbar reestruturada em grupos start/center/end com ações icon-only e hints acessíveis;
- Desktop/Tablet/Mobile passam a ícones compactos;
- Elementos e Propriedades passam a funcionar explicitamente em desktop/mobile;
- Configurações da página passa a abrir Conteúdo e reposicionar o Inspector;
- Auditar passa a abrir Avançado e exibir imediatamente o score;
- menu de overflow `…` mantém ações secundárias acessíveis em telas menores;
- Fechar, Publicar e Recuperação permanecem visíveis como ações críticas;
- HTML Surface do Scheduler Pro passa a expandir sua altura no editor em vez de ficar limitado a 760 px;
- medição do HTML importado usa iframe sem scripts (`allow-forms allow-same-origin`) somente no editor;
- conteúdos com classes comuns de reveal/scroll-animation são forçados visíveis apenas dentro do editor, sem alterar o HTML armazenado/publicado;
- nova identidade visual oficial AVB com símbolo/logo e paleta cyan/blue/violet;
- assets de branding passam a fazer parte do pacote NPM e do instalador Scheduler Pro;
- suíte ampliada para 48 testes automatizados.

## 2.1.0 — UX, Importação Scheduler Pro e Recuperação de Emergência

- corrigido o Inspector da página: Conteúdo, Estilo, Avançado e Histórico agora renderizam seus painéis corretos sem depender de elemento selecionado;
- reduzidos pesos tipográficos e densidade visual do editor;
- tema claro/escuro com persistência local e preferência do sistema;
- scrollbars verticais/horizontais discretas em todos os painéis roláveis;
- layout responsivo do editor refeito para telas menores, com drawers laterais a partir de 980 px;
- importador ZIP nativo para `scheduler-pro-template-package/v1`;
- importação/preservação de HTML `scheduler-pro-html-template/v1` como `html_surface`;
- normalização de wrappers HTML recebidos diretamente da API do Scheduler Pro;
- sete pacotes reais Scheduler Pro validados em Landing + Booking;
- SchedulerProAdapter ganha `emergencyRollback()` e `emergencyBlank()`;
- instalador Scheduler Pro adiciona snapshots imutáveis de publicação e endpoints de recuperação de emergência;
- `Reverter publicação` restaura a última publicação segura;
- `Publicar página em branco` publica HTML vazio seguro sem apagar versões;
- integração continua New-Only, sem editor/renderer legado no runtime;
- suíte ampliada para 42 testes automatizados.

## 2.0.1 — New-Only

- Scheduler Pro passa a usar exclusivamente o ARGWS Visual Builder Universal 2.0.
- removida feature flag `VITE_VISUAL_PAGE_BUILDER`;
- instalador remove os componentes de editor/renderer antigos após backup;
- renderer universal normaliza documentos V1/V2 automaticamente;
- `blocks` V2 permanece somente como projeção contratual do backend;
- documentação revisada para não sugerir rollback para editor anterior.

## 2.0.0 — 2026-08-27

- schema universal `argws-visual-builder/v3`, document version 4 e migração automática de V1/V2;
- 74 widgets nativos;
- Nested Tabs, Nested Accordion, Mega Menu, Floating Bar, TOC, Search, Share Buttons, Map, Lottie, Hotspot, Flip Box, Slides, Login, Cookie Consent e Code Block;
- Commerce provider-driven: product grid, product, cart, checkout e account;
- Dynamic Tag Registry e filtros encadeáveis;
- Data Source Registry, Query Loop assíncrono e QueryCache;
- Form Builder com schema JSON, campos avançados e fluxo multi-etapa;
- Submission Store memory/REST, action `collect_submission` e export CSV;
- Interactions por elemento e custom attributes em whitelist;
- Host Services para integrações de infraestrutura/negócio;
- Plugin SDK universal;
- Asset Library e `@font-face` seguro;
- i18n por documento/nó;
- Role/Capability Policy aplicada a operações do editor;
- operações incrementais com revisão para base de colaboração;
- Project Package para transportar site completo;
- Custom Code com política trusted/opt-in;
- snippets para HTML, Blade, PHP, Jinja2, Twig, Vue, React e Svelte;
- exemplos adicionais PHP, HTML, Blade, Jinja2, Twig, Node/Express, React e Svelte;
- compilador Scheduler Pro continua emitindo Landing V2 com metadata Universal V3;
- integração Scheduler Pro atualizada para 2.0.0 e reconhecimento V1/V2/V3;
- 39 testes automatizados.

## 1.0.0 — 2026-08-26

- schema `argws-visual-builder/v2`;
- editor visual Pro, responsividade, design system, conteúdo dinâmico, loops, forms, popups, SiteKit e integração Scheduler Pro;
- 20 testes automatizados.

## 0.1.0 — 2026-08-26

- primeira versão funcional.

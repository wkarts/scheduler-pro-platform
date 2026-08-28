# Arquitetura técnica — ARGWS Visual Builder 1.0

## 1. Princípio central

O editor não conhece FastAPI, Laravel, Node, WordPress ou banco de dados. Ele opera sobre um documento JSON canônico e delega persistência, upload, versões e ações ao host/adapters.

Isso evita acoplamento entre o editor visual e as regras de negócio do produto onde ele é instalado.

## 2. Documento e AST

Schema canônico atual:

```text
argws-visual-builder/v2
version: 3
```

`builder.nodes` é um mapa por ID. `builder.root_ids` controla a ordem no nível raiz. Cada node possui `children`, permitindo containers aninhados sem duplicação de objetos.

Campos de node relevantes:

```text
props               -> conteúdo estático
style               -> estilo base
states              -> hover/focus/active
responsive          -> overrides por breakpoint + hidden
responsive_states   -> estados por breakpoint
bindings            -> props ligadas a contexto dinâmico
conditions          -> regras de exibição
motion              -> entrance/sticky/runtime visual
children            -> IDs filhos
meta                -> classes, anchor e metadados extensíveis
```

Vantagens:

- IDs estáveis;
- operações de mover/duplicar/excluir previsíveis;
- histórico serializável;
- documentos fáceis de versionar;
- conteúdo dinâmico sem misturar regra de negócio com HTML;
- renderização independente do editor;
- compilação para contratos legados.

## 3. Design System e responsividade

O documento contém `design_system.breakpoints`, `design_system.variables` e `design_system.classes`.

A resolução responsiva é cascata do maior breakpoint para o menor. Com os defaults:

```text
Desktop = style
Tablet  = style + responsive.tablet
Mobile  = style + responsive.tablet + responsive.mobile
```

Breakpoints adicionais podem ser inseridos entre esses níveis. Estados pseudo seguem a mesma cascata por `responsive_states`.

O renderer público usa os breakpoints do próprio documento, enquanto o editor usa o `canvas` de cada breakpoint para preview previsível.

## 4. Persistência

Adapter é a fronteira entre browser e aplicação:

```text
load()
saveDraft(document)
autosave(document)
publish(document)
listTemplates?()
versions?()
restoreVersion?()
upload?()
```

O core não deve armazenar autoridade de tenant, permissão ou segredo. Autenticação e autorização permanecem no backend/host.

## 5. Renderer e runtime

O renderer é uma função pura de documento + contexto e produz HTML/CSS. Interações são hidratadas separadamente pelo runtime.

Isso permite que builds públicos importem apenas o necessário e não enviem o editor ao visitante final.

Runtime atual:

- popup/offcanvas;
- tabs;
- carousel;
- lightbox;
- counter;
- countdown;
- forms/actions.

## 6. Conteúdo dinâmico

`bindings` ligam uma prop a um caminho no contexto, por exemplo:

```text
props.title = fallback
bindings.title = tenant.public_name
```

Textos também podem interpolar `{{tenant.public_name}}`.

`conditions` recebem o mesmo contexto e decidem se o node será renderizado. `loop` recebe uma coleção por caminho e cria um contexto `item` para cada repetição.

Nenhuma query de banco é executada pelo core. O host fornece os dados já autorizados.

## 7. SiteKit

`SiteKit` é o equivalente genérico do conceito de Theme Builder. Partes globais podem ser cadastradas como:

```text
header
footer
single
archive
```

Cada parte possui prioridade e conditions. O host resolve o contexto da rota e escolhe as partes aplicáveis.

## 8. Scheduler Pro

O Scheduler Pro continua recebendo uma projeção do contrato atual:

```text
version = 2
global_styles
seo
blocks
builder
```

`builder` mantém a árvore canônica avançada; `blocks` é somente a projeção de compatibilidade exigida pelo contrato atual da API do Scheduler Pro.

O Scheduler Pro usa sempre `PublicVisualLandingRenderer`. Documentos antigos sem `builder.schema` são normalizados a partir de `blocks` pelo próprio `normalizeDocument()` antes da renderização. O widget de agenda não implementa agendamento: ele fornece o ponto de integração para o `PublicBookingWidget` real do Scheduler Pro.

## 9. Extensões

Há registries independentes para:

```text
widgets
renderers
actions
```

Assim, módulos específicos de negócio ficam fora do core:

```text
Scheduler Pro -> booking, services, professionals
ERP           -> product_catalog, quote_form
Financial     -> payment_link, billing_form
Support       -> ticket_form, knowledge_search
```

## 10. Compatibilidade

O migrador aceita documentos `argws-visual-builder/v1` e normaliza para v2. Nenhum documento deve ser sobrescrito silenciosamente no backend sem versionamento; o adapter deve criar revisão/rascunho antes de publicar.

A compatibilidade com hosts legados é feita por compiladores/adapters, não degradando o schema canônico para caber no backend.

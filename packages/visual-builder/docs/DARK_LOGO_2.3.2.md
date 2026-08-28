# ARGWS Visual Builder 2.3.2 — Logo oficial Light/Dark

## Objetivo

Integrar o asset dark oficial fornecido ao sistema de temas existente sem alterar a identidade visual, os ícones ou a arquitetura da aplicação.

## Regra

| Tema AVB | Asset |
| --- | --- |
| Light | `assets/brand/argws-visual-builder-logo-1600.png` |
| Dark | `assets/brand/argws-visual-builder-logo-dark.png` |

O arquivo dark é copiado integralmente para a distribuição. Não há processamento de cor, geração de SVG, recorte, reconstrução ou criação automática de novas variantes.

## Onde a seleção é aplicada

- Visual Editor (`<argws-visual-builder>`);
- Project/Site Workspace (`<argws-visual-builder-app>`).

Esses são os pontos de branding pertencentes ao núcleo atual. Qualquer host que reutilize esses componentes herda automaticamente a regra, inclusive Scheduler Pro, Laravel/Blade, PHP, FastAPI/Jinja, Vue, React, Svelte e integrações REST.

## Layout compacto

Em breakpoints onde o wordmark completo ocuparia espaço excessivo, a UI continua usando o símbolo AVB já existente. Isso não é uma variante de logo dark: é o mesmo ícone/símbolo utilizado antes da 2.3.2 e permanece inalterado.

## O que não mudou

- favicon;
- símbolos/ícones AVB;
- ícones funcionais da toolbar;
- SVGs;
- Design System de páginas editadas;
- tema das páginas do cliente;
- schema `argws-visual-builder-project/v2`;
- schema de documento;
- adapters e Plugin SDK;
- renderer público;
- integração de regras de negócio do Scheduler Pro.

## Implementação

O código resolve a URL do wordmark pelo helper compartilhado `resolveAvbBrandLogo(theme)` e expõe `AVB_BRAND_ASSETS` para shells externos do próprio produto. Editor e Project/Site Workspace consomem o mesmo helper; não foi criado um segundo sistema de tema.

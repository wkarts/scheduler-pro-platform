# Release Validation — ARGWS Visual Builder Universal 2.3.1

## Escopo

Release incremental de Brand Alignment sobre a arquitetura 2.3.0. Não altera modelo de dados nem integração funcional.

## Validação executada

- `npm run check`: **OK**;
- `npm test`: **60/60 OK**;
- importação do módulo raiz em Node/SSR: **OK**;
- `npm pack`: **OK**;
- instalação do TGZ em projeto Node vazio: **OK**;
- importação pelo pacote instalado: **OK**;
- instalador Scheduler Pro executado duas vezes sobre fixture compatível: **OK / idempotente**;
- dependência `@argws/visual-builder` atualizada para `2.3.1` na fixture: **OK**;
- schema Project/Site v2: **OK**;
- PageDocument VISUAL/HTML: **OK**;
- migração `html_surface` legado → PageDocument HTML: **OK**;
- adapters universais e Scheduler Pro: **OK**;
- importação Scheduler Pro LANDING/BOOKING como páginas independentes: **OK**.

## Testes adicionais 2.3.1

Foram adicionados sete testes específicos:

1. paleta oficial AVB exata;
2. Space Grotesk em headings e Inter no body da interface;
3. isolamento tipográfico do renderer público;
4. contraste WCAG AA nos pares essenciais de Light/Dark;
5. ação primária sem branco diretamente sobre Cyan;
6. sincronização/persistência Light/Dark no Project Workspace + Editor;
7. nenhum peso tipográfico da UI acima de 700.

## Contraste

Todos os pares críticos testados possuem contraste >= 4.5:1 para texto normal.

## Fontes

Nenhum arquivo de fonte é empacotado e nenhuma CDN obrigatória foi adicionada. `Space Grotesk` usa fallback seguro para `Inter`/system-ui quando não disponível no host.

## Risco de regressão

Baixo: mudanças concentradas em tokens CSS, hierarquia tipográfica e tema do Project Workspace. Renderer público, schema, adapters, plugins e persistência não foram alterados.

## Navegador

A suíte automatizada cobre estrutura e contratos de UI. Esta release não declara um novo E2E Chromium real executado nesta sessão; recomenda-se smoke visual em navegador no pipeline/projeto hospedeiro para conferir diferenças de renderização de fontes instaladas.

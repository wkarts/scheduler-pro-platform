# ARGWS Visual Builder 2.3.1 — Runtime Fix

## Diagnóstico de produção

O pacote `scheduler-pro-diagnostics-20260828-114106Z.zip` registrou cinco ocorrências idênticas no tenant, todas em `#visual-builder`:

`NotSupportedError: Failed to execute 'createElement' on 'Document': The result must not have attributes`

A causa estava em `ArgwsVisualBuilderApp`: o construtor do Custom Element gravava `data-project-theme` antes do elemento terminar de ser criado. Chromium rejeita Custom Elements que retornam do construtor já com atributos adicionados pela própria classe.

## Correção

- o `constructor()` do `argws-visual-builder-app` não modifica mais atributos;
- `data-project-theme` é aplicado em `connectedCallback()`;
- `disconnectedCallback()` restaura corretamente o estado reconectável;
- foi criado teste de regressão específico para impedir atributos no construtor;
- o mount Vue do Builder agora possui try/catch e tela interna de recuperação, evitando overlay vazio travando o tenant;
- `ArgwsPageRenderer` só renderiza após estar conectado ao DOM, evitando renders duplicados durante criação;
- o compilador Scheduler Pro agora atualiza metadados mínimos de HTML legado somente quando estiverem ausentes/incompatíveis, preservando HTML já válido byte a byte.

## Control Plane

Os diagnósticos também mostraram resposta de observabilidade com cerca de 1 MB e warning do Nginx de buffering em arquivo temporário. O Control Plane solicitava até 1000 logs e podia repetir isso a cada 5 segundos.

Correção:

- limite do painel: 300 eventos;
- auto-refresh: 15 segundos;
- nenhum refresh novo inicia enquanto o anterior ainda estiver em andamento;
- auto-refresh pausa quando a aba do navegador não está visível.

## Polling do tenant

O polling de status do WhatsApp passa a:

- usar intervalo de 10 segundos;
- pausar enquanto o Visual Builder estiver aberto;
- pausar quando a página estiver em background.

## PWA/cache

Os caches do Service Worker de tenant e Control Plane foram versionados novamente para obrigar a retirada dos bundles anteriores após deploy.

## Erros de storage no console

Os nomes `spa-maker.js`, `wrapper-cuponomia-ads.js` e `notifications.js` não existem no Scheduler Pro. São scripts de extensões do navegador injetados no iframe sandboxed. O sandbox continua isolado intencionalmente; não foi adicionado `allow-same-origin` junto com scripts, pois isso enfraqueceria a segurança dos templates.

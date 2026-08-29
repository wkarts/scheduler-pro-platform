# Padrão de construção de templates — AVB 2.4.0

Este documento é o contrato técnico resumido para desenvolvimento manual ou por IA.

## Regra de ouro

O template controla a experiência visual. O host controla autenticação, regras de negócio, dados sensíveis e integrações.

## Estrutura obrigatória

```text
experience.json
bindings.json
theme.json
pages/landing.html
pages/booking.html
assets/
```

Não criar `login.html`.

## HTML

Pode utilizar HTML5, CSS moderno, JavaScript seguro, SVG, Canvas, Web Components, Lottie e animações. Não há obrigação de usar componentes genéricos do AVB.

## Bindings

Tudo que o cliente poderá editar sem alterar estrutura deve ser declarado em `bindings.json` e marcado com `data-sp-bind`, `data-sp-show` ou `data-sp-list`.

## Agenda

A página Booking deve usar `ARGWSRuntime.booking.*`. Nunca codificar endpoints internos do Scheduler Pro.

## Assets

Imagens grandes devem ficar em `assets/`. Evitar Base64 para imagens pesadas.

## Analytics

Eventos devem usar `ARGWSRuntime.analytics.track()`. Pixel/GA/GTM são responsabilidade do host.

## Segurança

Nunca incluir senha, token, secret, credencial, `eval`, `new Function`, script ofuscado ou autenticação paralela.

## Compatibilidade

O visual final deve funcionar sem etapa de build obrigatória. Caso Astro/Svelte/Vue/React sejam usados na autoria, entregar apenas o output compilado final.

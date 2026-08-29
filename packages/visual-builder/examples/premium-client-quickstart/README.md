# Premium Client Quickstart — Experience Contract v2

Exemplo prático para iniciar um novo cliente no **ARGWS Visual Builder 2.4.0** sem depender de compilação no runtime.

## O que este pacote demonstra

- Landing HTML completa e responsiva.
- Agenda Pública HTML completa.
- `experience.json` com somente `LANDING` e `BOOKING`.
- `bindings.json` para editar conteúdo sem reconstruir o HTML.
- `theme.json` para design tokens.
- assets físicos em `assets/`.
- `ARGWSRuntime.context` para obter contexto do host.
- `ARGWSRuntime.navigation` para navegar sem hardcode da aplicação.
- `ARGWSRuntime.booking` para usar o motor real de agendamento.
- `ARGWSRuntime.analytics` para eventos de conversão.
- nenhum `login.html`.
- nenhum endpoint interno do Scheduler Pro dentro do template.

## Fluxo recomendado para criar um novo cliente

1. Duplique este pacote.
2. Troque `package.key`, nome e descrição em `experience.json`.
3. Substitua logo, hero e demais arquivos em `assets/`.
4. Mantenha os bindings existentes ou declare novos em `bindings.json`.
5. Personalize os tokens de `theme.json`.
6. Preserve `ARGWSRuntime.booking.*` na página de Agenda.
7. Preserve `data-sp-action` e `data-sp-bind`.
8. Valide o ZIP pelo Experience Contract v2 antes da publicação.

## Landing

A Landing pode ter qualquer direção visual: minimalista, futurista, glassmorphism, editorial, premium, automotiva, clínica, beleza etc. O Visual Builder não deve desmontar a página; ele altera somente bindings declarados.

```html
<h1 data-sp-bind="hero.title">Título</h1>
<img data-sp-bind="brand.logo" src="../assets/logo.svg" alt="">
<a data-sp-action="booking" href="/agendar">Agendar</a>
```

## Agenda Pública

O visual é do template, mas a lógica pertence ao host.

```js
await ARGWSRuntime.booking.catalog()
await ARGWSRuntime.booking.availability({ service_id, date })
await ARGWSRuntime.booking.create(payload)
```

Nunca grave endpoints internos como `/api/v1/...` dentro do template.

## Login

Não crie `login.html`. O Login é nativo do Scheduler Pro/host e recebe branding white-label.

## Assets

Para novos trabalhos prefira WebP/AVIF para imagens grandes, SVG para vetores, PNG para transparência e JPEG quando apropriado. Base64 existe para compatibilidade de migração.

## Antes de entregar

- [ ] `experience.json` usa `argws-experience-package/v2`;
- [ ] Landing abre sem dependência do backend;
- [ ] Agenda usa `ARGWSRuntime.booking`;
- [ ] nenhum endpoint interno está hardcoded;
- [ ] não existe `login.html`;
- [ ] imagens grandes estão em `assets/`;
- [ ] bindings correspondem aos elementos HTML;
- [ ] tema usa tokens;
- [ ] mobile está responsivo;
- [ ] CTA Landing → Agenda funciona;
- [ ] analytics usa `ARGWSRuntime.analytics.track`;
- [ ] identidade do cliente não está presa à marca Scheduler Pro.

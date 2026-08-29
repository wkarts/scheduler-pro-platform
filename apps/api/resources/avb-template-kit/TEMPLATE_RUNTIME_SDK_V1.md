# Template Runtime SDK v1 — ARGWS Visual Builder 2.4.0

A **Template Runtime SDK v1** é a camada estável entre um template HTML e a aplicação hospedeira. O template não conhece FastAPI, Laravel, Vue, banco de dados, tokens, URLs internas ou detalhes de autenticação.

## Regra de arquitetura

```text
Template HTML/CSS/JS
        ↓
ARGWSRuntime
        ↓
Host Adapter
        ↓
Aplicação hospedeira
```

No Scheduler Pro, o host implementa booking, branding, navegação e analytics. Em outro sistema, o mesmo template pode usar outro adapter.

## API pública

### Contexto

```js
const context = await ARGWSRuntime.context.get()
```

Retorna contexto seguro do host, por exemplo tenant/empresa, locale, timezone, superfície atual e flags públicas.

### Branding

```js
const branding = await ARGWSRuntime.branding.get()
```

Retorna somente identidade visual pública: nome, logos, cores, favicon/ícones publicados e tokens permitidos.

### Features

```js
const features = await ARGWSRuntime.features.get()
```

Use para renderização condicional sem codificar regras de negócio no HTML.

### Booking

```js
const catalog = await ARGWSRuntime.booking.catalog()
const slots = await ARGWSRuntime.booking.availability({ service_id, professional_id: null, date: "2026-08-29" })
const appointment = await ARGWSRuntime.booking.create({
  service_id,
  professional_id: null,
  starts_at,
  customer: { name, phone, email }
})
await ARGWSRuntime.booking.cancel({ appointment_id: appointment.id })
await ARGWSRuntime.booking.reschedule({ appointment_id: appointment.id, starts_at: nextStart })
```

O template controla layout e experiência. O host controla disponibilidade, capacidade, persistência, validação, timezone e segurança.

### Navegação

```js
await ARGWSRuntime.navigation.openLanding()
await ARGWSRuntime.navigation.openBooking()
await ARGWSRuntime.navigation.navigate({ to: "/pagina" })
```

### Analytics

```js
await ARGWSRuntime.analytics.track("booking_started", { service_id })
await ARGWSRuntime.analytics.track("booking_completed", { appointment_id })
```

O template emite eventos semânticos. Google Analytics, Google Ads, Meta Pixel, GTM e outros providers são configurados pelo host.

## Eventos recomendados

- `page_view`
- `booking_started`
- `service_selected`
- `professional_selected`
- `date_selected`
- `slot_selected`
- `booking_completed`
- `booking_failed`
- `whatsapp_clicked`
- `phone_clicked`
- `instagram_clicked`
- `cta_clicked`

## Host Adapter

```js
import { installTemplateRuntimeGlobal } from "@argws/visual-builder"

installTemplateRuntimeGlobal({
  async getContext() {},
  async getBranding() {},
  async getFeatures() {},
  async bookingCatalog() {},
  async bookingAvailability(input) {},
  async bookingCreate(input) {},
  async bookingCancel(input) {},
  async bookingReschedule(input) {},
  async navigate(input) {},
  async track(input) {},
}, "ARGWSRuntime")
```

## Regras de segurança

- nunca expor senha, token ou secret ao template;
- templates não implementam autenticação paralela;
- templates não chamam endpoints internos hardcoded;
- templates não acessam banco/storage diretamente;
- não usar `eval`, `new Function` ou código ofuscado;
- analytics sempre via `ARGWSRuntime.analytics.track()`;
- permissões e rate limiting pertencem ao host.

## Compatibilidade

HTML é o runtime canônico. Astro, Svelte, Vue, React ou outra tecnologia podem ser usadas na autoria desde que o pacote final entregue HTML/CSS/JS/assets compatíveis com o Experience Contract v2.

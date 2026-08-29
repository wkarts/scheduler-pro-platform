# Template Runtime SDK v1

A SDK abstrai o host. O template não conhece URLs internas, tokens, FastAPI, Laravel, Vue ou bancos de dados.

## API estável

```js
const ctx = await ARGWSRuntime.context.get()
const brand = await ARGWSRuntime.branding.get()
const features = await ARGWSRuntime.features.get()

const catalog = await ARGWSRuntime.booking.catalog()
const slots = await ARGWSRuntime.booking.availability({ service_id, date })
const appointment = await ARGWSRuntime.booking.create(payload)

await ARGWSRuntime.navigation.openBooking()
await ARGWSRuntime.analytics.track('booking_completed', { appointment_id })
```

## Host Adapter

Uma aplicação integra o SDK fornecendo funções:

```js
const sdk = createTemplateRuntimeSdk({
  getContext,
  getBranding,
  getFeatures,
  bookingCatalog,
  bookingAvailability,
  bookingCreate,
  bookingCancel,
  bookingReschedule,
  navigate,
  track
})
```

Somente `getContext`, `bookingCatalog`, `bookingAvailability` e `bookingCreate` são obrigatórios para uma experiência de agendamento completa.

## Segurança

Templates não recebem segredos do backend. O host controla autenticação, CORS, tokens, permissões, rate limiting e políticas de dados.

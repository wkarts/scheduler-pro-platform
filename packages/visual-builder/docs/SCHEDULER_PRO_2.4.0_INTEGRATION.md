# Scheduler Pro + ARGWS Visual Builder 2.4.0

O ARGWS Visual Builder 2.4.0 é universal. O Scheduler Pro é um host que injeta contexto, branding, booking, navegação e analytics por meio do **Template Runtime SDK v1**.

## Superfícies editáveis

- LANDING `/pagina` — HTML completo, Bindings v1, Theme Tokens v1.
- BOOKING `/agendar` — HTML completo, Bindings v1, Theme Tokens v1 e Booking SDK.
- LOGIN `/login` — **não é template**. É a tela nativa do Scheduler Pro, white-label por Branding/Theme Tokens.

## Experience Package v2

```text
experience.json
bindings.json
theme.json
pages/landing.html
pages/booking.html
assets/...
```

O contrato não exige compilação. Templates podem ser escritos diretamente em HTML/CSS/JS. Astro, Svelte, Vue ou React podem ser usados como tecnologia de autoria desde que a entrega ao Scheduler Pro seja o output HTML/CSS/JS final.

## Runtime SDK

O host deve implementar:

- `getContext()`
- `getBranding()`
- `getFeatures()`
- `bookingCatalog()`
- `bookingAvailability()`
- `bookingCreate()`
- `navigate()`
- `track()`

O template usa apenas `ARGWSRuntime` e nunca endpoints internos.

## Login

O Login do Scheduler Pro é nativo e recebe:

- logo;
- favicon;
- cores;
- tipografia;
- background opcional;
- título/subtítulo;
- identidade PWA.

Autenticação, 2FA, refresh, sessão e recuperação continuam centralizados no Scheduler Pro.

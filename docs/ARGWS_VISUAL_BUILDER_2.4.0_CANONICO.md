# ARGWS Visual Builder 2.4.0 — arquitetura canônica no Scheduler Pro

## Direção oficial

O ARGWS Visual Builder 2.4.0 é um núcleo universal. O Scheduler Pro utiliza um adapter/host próprio e não acopla regras de agenda/autenticação ao core do Builder.

### Landing Page
- HTML/CSS/JS completos como runtime canônico.
- bindings editáveis sem reconstruir a página em widgets genéricos.
- assets externos.
- Theme Tokens.
- preview, rascunho, versionamento e publicação.

### Agenda Pública
- HTML/CSS/JS completos.
- bindings editáveis.
- motor real do Scheduler Pro através do Template Runtime SDK.
- catálogo, disponibilidade, criação, cancelamento e reagendamento fornecidos pelo host.

### Login
- não é template HTML.
- permanece nativo e seguro no Scheduler Pro.
- white-label: logo, favicon, cores, fundo e textos.
- autenticação, refresh, sessão, 2FA e recuperação continuam centralizados.

### Identidade Visual e PWA
- branding central por tenant.
- logo claro/escuro, favicon, ícone PWA e fundo do Login podem ser enviados pelo tenant ou pelo Control Plane.
- manifest por tenant e `start_url` apropriado para PWA.
- a nova identidade Scheduler Pro é o fallback quando o tenant não personalizou sua marca.

## Experience Contract v2

Estrutura recomendada:

```text
experience.json
bindings.json
theme.json
pages/landing.html
pages/booking.html
assets/...
```

Não existe `login.html` no contrato v2.

## Compatibilidade v1

Pacotes `scheduler-pro-template-package/v1` continuam aceitos por uma camada de migração. Imagens Base64 grandes são extraídas automaticamente para assets deduplicados por SHA-256 e as referências são reescritas sem reconstruir o layout.

Templates antigos não precisam ser refeitos manualmente somente por utilizarem Base64.

Para novos templates, use arquivos físicos em `assets/`. Formatos recomendados:
- WebP/AVIF para fotos e imagens grandes;
- SVG para vetores/ícones;
- PNG quando transparência/raster for necessária;
- JPEG quando apropriado.

## Permissões do Visual Builder

Níveis: `blocked`, `basic`, `design`, `full`, `developer`.

O Control Plane pode administrar páginas, bindings, branding e permissões mesmo quando o editor está bloqueado para o tenant.

## Correções funcionais desta rodada

- CRUD completo de faixas de expediente.
- CRUD completo de períodos de bloqueio.
- agendamentos antigos não desaparecem por INNER JOIN com cadastros ausentes.
- fallback de duração para registros legados sem `ends_at`.
- calendário mobile sem largura mínima desktop.
- menu do tenant em mobile usa drawer/backdrop próprios.
- Branding/PWA renovados com nova identidade padrão Scheduler Pro.
- Experience Contract v2 com migração Base64 → assets.
- Landing/Booking utilizam Runtime SDK; Login permanece nativo.

## Template Runtime SDK v1

O host pode fornecer:

```text
context.get
branding.get
features.get
booking.catalog
booking.availability
booking.create
booking.cancel
booking.reschedule
navigation.open
analytics.track
```

Templates não devem hardcodar endpoints internos.

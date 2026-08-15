# API

Prefixo oficial:

```text
/api/v1
```

Padrão de sucesso:

```json
{"data": {}, "meta": {}}
```

Padrão de erro:

```json
{"error": {"code": "APPOINTMENT_SLOT_UNAVAILABLE", "message": "Horário não disponível.", "details": {}}}
```

Tags OpenAPI:

- Authentication
- Customers
- Appointments
- Services
- Professionals
- Landing Pages
- Branding / White Label
- WhatsApp
- Files
- Platform

## Branding / White Label

Endpoints tenant-aware. O tenant é resolvido pelo hostname, não por `tenant_id` enviado no frontend.

```text
GET  /api/v1/branding/manifest
PUT  /api/v1/branding/profile
POST /api/v1/branding/publish
POST /api/v1/branding/build-profiles
```

### Manifesto

```json
{
  "tenant": {"id": "...", "slug": "barbearia", "hostname": "barbearia.scheduler.com.br"},
  "app": {"name": "Barbearia", "public_name": "Barbearia do João", "slogan": "Agende seu horário", "locale": "pt-BR", "timezone": "America/Bahia"},
  "assets": {"logo_url": "...", "icon_url": "...", "favicon_url": "..."},
  "theme": {
    "mode": "system",
    "font_family": "Inter, ui-sans-serif, system-ui",
    "border_radius": "1rem",
    "colors": {"primary": "#0f172a", "secondary": "#22d3ee", "accent": "#38bdf8", "background": "#020617", "text": "#f8fafc"}
  },
  "settings": {},
  "status": "PUBLISHED",
  "published_at": "2026-08-15T08:00:00Z"
}
```

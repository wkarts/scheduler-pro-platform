# White-label por tenant

O white-label do Scheduler Pro é um domínio de primeira classe do Control Plane e não deve ser tratado como configuração solta no frontend.

## Componentes

```text
Tenant
  ├─ TenantBrandingProfile
  ├─ TenantBrandingAsset
  ├─ BuildProfile
  ├─ Domain
  └─ LandingPage
```

## Resolução

A personalização é descoberta a partir do hostname resolvido pelo `TenantResolver`:

```text
Request Host
  -> TenantResolver
  -> TenantContext
  -> /api/v1/branding/manifest
  -> Web/PWA/Desktop/Mobile aplica tokens visuais
```

O frontend não envia `tenant_id` como autoridade. O `tenant_id` do manifesto é informativo e derivado do contexto resolvido pelo backend.

## Manifesto

Endpoint:

```text
GET /api/v1/branding/manifest
```

Contrato:

```json
{
  "tenant": {"id":"...", "slug":"...", "hostname":"..."},
  "app": {"name":"...", "public_name":"...", "slogan":"...", "locale":"pt-BR", "timezone":"America/Bahia"},
  "assets": {"logo_url":"...", "icon_url":"...", "favicon_url":"..."},
  "theme": {
    "mode":"system",
    "font_family":"Inter, ui-sans-serif, system-ui",
    "border_radius":"1rem",
    "colors": {
      "primary":"#0f172a",
      "secondary":"#22d3ee",
      "accent":"#38bdf8",
      "background":"#020617",
      "text":"#f8fafc"
    }
  },
  "settings": {},
  "status":"PUBLISHED",
  "published_at":"..."
}
```

## Landing page

A landing page continua versionada separadamente:

```text
landing_pages
landing_page_versions
```

Ela deve consumir o branding publicado do tenant para renderização pública, mas seu conteúdo editorial permanece versionado no banco do tenant.

## Build profiles

`build_profiles` armazena configuração para diferentes entregas:

- `web`;
- `pwa`;
- `desktop`;
- `android`;
- `ios`.

Campos importantes:

```json
{
  "name":"Barbearia do João Desktop",
  "target":"desktop",
  "bundle_identifier":"br.com.empresa.scheduler",
  "package_name":"br.com.empresa.scheduler",
  "api_url":"https://agenda.empresa.com.br/api/v1",
  "features": ["whatsapp", "appointments"],
  "config": {}
}
```

## Estados

Branding:

```text
DRAFT
PUBLISHED
ARCHIVED
```

Build profile:

```text
ativo por registro e versão futura por Build Manager
```

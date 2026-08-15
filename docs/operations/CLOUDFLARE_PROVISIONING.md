# Cloudflare, provisionamento e domínios

O Scheduler Pro agora possui estrutura operacional para provisionar clientes/tenants com:

- domínio temporário `<slug>.<TENANT_DEFAULT_DOMAIN_ROOT>`;
- Cloudflare DNS record para domínios da própria plataforma;
- Cloudflare for SaaS Custom Hostname para domínio próprio do cliente;
- branding/white-label inicial por tenant;
- perfis de build `web`, `pwa`, `desktop`, `android` e `ios`;
- endpoint público `/api/v1/public/landing` para a página pessoal do tenant.

## Variáveis principais

```env
PUBLIC_PLATFORM_DOMAIN=scheduler.argws.com.br
TENANT_DEFAULT_DOMAIN_ROOT=scheduler.argws.com.br
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_ZONE_ID=...
CLOUDFLARE_DRY_RUN=false
CLOUDFLARE_TEMPORARY_RECORD_TYPE=CNAME
CLOUDFLARE_TEMPORARY_RECORD_TARGET=proxy.scheduler.argws.com.br
CLOUDFLARE_CUSTOM_HOSTNAME_ORIGIN=proxy.scheduler.argws.com.br
```

Use `CLOUDFLARE_DRY_RUN=true` em homologação para validar fluxo sem chamar a API externa.

## Endpoints Control Plane

```http
POST /api/v1/platform/tenants
GET  /api/v1/platform/tenants
GET  /api/v1/platform/domains
POST /api/v1/platform/tenants/{tenant_id}/domains/temporary
POST /api/v1/platform/tenants/{tenant_id}/domains/custom
POST /api/v1/platform/domains/{domain_id}/check
POST /api/v1/platform/domains/{domain_id}/purge-cache
```

## Landing pública

```http
GET /api/v1/public/landing?slug=home
```

A resposta contém `branding` e `landing_page`, resolvidos pelo hostname recebido na requisição.

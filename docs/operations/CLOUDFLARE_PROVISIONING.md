# Cloudflare, provisionamento e domínios

O Scheduler Pro possui estrutura operacional para provisionar clientes/tenants com:

- domínio temporário `<slug>.<TENANT_DEFAULT_DOMAIN_ROOT>`;
- Cloudflare DNS record para domínios da própria plataforma;
- Cloudflare for SaaS Custom Hostname para domínio próprio do cliente;
- branding inicial por tenant;
- perfis de build `web`, `pwa`, `desktop`, `android`, `ios` e variantes administrativas;
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

`CLOUDFLARE_ZONE_ID` é o identificador da **zone DNS**, não o Account ID. Se o valor estiver
incorreto, o backend valida a zone configurada e tenta resolver automaticamente a zone acessível
pelo token a partir do hostname da plataforma. Também é permitido deixar `CLOUDFLARE_ZONE_ID`
vazio quando o token possui `Zone:Read` e `CLOUDFLARE_CUSTOM_HOSTNAME_ORIGIN` está configurado.

O diagnóstico da integração passa a informar o Zone ID configurado e o Zone ID efetivamente
resolvido, evitando que um Account ID seja tratado silenciosamente como Zone ID.

## Permissões Cloudflare

Para DNS temporário e descoberta da zone:

- Zone Read;
- DNS Edit/Write.

Para o botão de purge de cache, o token também precisa de **Cache Purge**. Falta dessa permissão
não invalida o DNS nem o domínio do tenant; o backend retorna `CLOUDFLARE_CACHE_PURGE_PERMISSION_ERROR`
especificamente para a operação de purge.

Custom Hostnames/SSL de domínio próprio dependem ainda dos recursos e permissões de Cloudflare for
SaaS disponíveis na conta.

Use `CLOUDFLARE_DRY_RUN=true` em homologação para validar fluxo sem chamar a API externa.

## Domínio temporário x domínio próprio

Domínio temporário da plataforma:

```text
cliente.scheduler.argws.com.br -> proxy.scheduler.argws.com.br
```

Este fluxo usa um registro DNS comum da zone da plataforma. Se o CNAME existe com o target
esperado, o domínio é considerado `ACTIVE`.

Domínio próprio do cliente:

```text
agenda.cliente.com.br -> proxy.scheduler.argws.com.br
```

Este fluxo usa Custom Hostnames/SSL quando o recurso está disponível.

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

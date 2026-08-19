# Scheduler Pro no CloudPanel

Este deployment foi desenhado para que a única ação manual no CloudPanel seja criar um Reverse Proxy para a stack Docker.

## Arquitetura

```text
Cloudflare DNS
  scheduler.argws.com.br
  *.scheduler.argws.com.br
          |
          v
CloudPanel / NGINX :443
          |
          v
http://127.0.0.1:18080
          |
          v
Scheduler Pro Docker
  scheduler-proxy -> API / Web / Admin
```

A stack inclui dois serviços auxiliares:

- `scheduler-acme`: cria/remover o TXT `_acme-challenge` pela API Cloudflare, emite `scheduler.argws.com.br` + `*.scheduler.argws.com.br` e renova o certificado automaticamente;
- `scheduler-cloudpanel-agent`: único container privilegiado. Não publica portas, não possui rede e usa o host montado somente para localizar o VHost do CloudPanel, adicionar o wildcard, validar `nginx -t` e instalar/renovar o certificado via `clpctl`.

## Única etapa manual

No CloudPanel crie um único Reverse Proxy:

```text
Domínio: scheduler.argws.com.br
Reverse Proxy URL: http://127.0.0.1:18080
```

Pode criar o Reverse Proxy antes ou depois de subir a stack. O agente fica aguardando até o VHost aparecer.

**Não é necessário:**

- editar o VHost manualmente;
- executar script no VPS;
- instalar `acme.sh` no host;
- criar cron no host;
- importar certificado manualmente;
- criar DNS, VHost ou certificado por tenant;
- criar TXT ACME manualmente.

## Subir a stack

```bash
docker compose --env-file .env -f compose.argws.yaml pull
docker compose --env-file .env -f compose.argws.yaml up -d --remove-orphans
```

No Dockge, use o mesmo `compose.argws.yaml` e `.env`.

## Cloudflare e DNS wildcard

Configure no `.env`:

```env
CLOUDFLARE_API_TOKEN=TOKEN_COM_ZONE_READ_E_DNS_EDIT
CLOUDFLARE_ZONE_NAME=argws.com.br
CLOUDFLARE_TEMPORARY_RECORD_PROXIED=false
CLOUDFLARE_MANAGED_WILDCARD_DNS=true
CLOUDFLARE_MANAGED_WILDCARD_TARGET=proxy.scheduler.argws.com.br
```

O backend garante:

```text
*.scheduler.argws.com.br CNAME proxy.scheduler.argws.com.br
proxied=false
```

Novos tenants são resolvidos pelo wildcard. Registros específicos legados são reconciliados para DNS-only quando existirem.

## ACME DNS-01 automático

O `scheduler-acme` usa o mesmo `CLOUDFLARE_API_TOKEN` da integração e solicita:

```text
scheduler.argws.com.br
*.scheduler.argws.com.br
```

O fluxo é automático:

```text
Let's Encrypt order
  -> challenge DNS-01
  -> dns_cf cria _acme-challenge.scheduler.argws.com.br TXT temporário
  -> Let's Encrypt valida
  -> dns_cf remove o TXT
  -> bundle atualizado em scheduler-pro-data/certs
```

O container verifica renovações periodicamente. Não há TXT ACME estático.

## Automação do CloudPanel

O `scheduler-cloudpanel-agent` aguarda o site `scheduler.argws.com.br` existir e então:

1. localiza o VHost em `/etc/nginx/sites-enabled`;
2. garante `server_name scheduler.argws.com.br *.scheduler.argws.com.br;`;
3. faz backup antes da alteração;
4. executa `nginx -t` e reverte se a validação falhar;
5. detecta mudança do hash do certificado;
6. chama `clpctl site:install:certificate` no host;
7. valida e recarrega o NGINX;
8. grava o marcador `last-cloudpanel-installed-at.txt` usado pelo diagnóstico da API.

O agente é propositalmente isolado:

```text
privileged: true
network_mode: none
sem portas publicadas
root filesystem read-only
```

Ele possui acesso de root ao host exclusivamente porque precisa executar o `clpctl` e reconciliar o VHost do NGINX. API, workers, banco, Redis, RabbitMQ e demais serviços continuam sem esse privilégio.

## Variáveis principais

```env
ACME_EMAIL=admin@scheduler.argws.com.br
ACME_DOMAIN=scheduler.argws.com.br
ACME_STAGING=false
ACME_DNS_SLEEP=20
ACME_CHECK_INTERVAL_SECONDS=43200

CLOUDPANEL_SITE_DOMAIN=scheduler.argws.com.br
CLOUDPANEL_WILDCARD_DOMAIN=*.scheduler.argws.com.br
CLOUDPANEL_SYNC_INTERVAL_SECONDS=60
```

## Resultado operacional

Depois de criar o Reverse Proxy e subir a stack:

```text
Novo tenant
  -> banco/migrations/admin/storage
  -> hostname do tenant
  -> DNS wildcard já resolve
  -> certificado wildcard já cobre
  -> VHost wildcard já aceita
  -> Scheduler Pro resolve pelo Host
  -> ACTIVE
```

Não existe ação CloudPanel por tenant e não existe renovação manual de certificado.

## Domínios externos

Um domínio como `agenda.cliente.com.br` não é coberto por `*.scheduler.argws.com.br`. Esse fluxo continua separado e exige TLS próprio.

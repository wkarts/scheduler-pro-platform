# Checklist — Scheduler Pro wildcard no CloudPanel

## Única ação manual

No CloudPanel crie/mantenha somente um Reverse Proxy:

```text
Domínio: scheduler.argws.com.br
URL: http://127.0.0.1:18080
```

Depois suba a stack completa no Dockge/Compose. Não execute script no VPS e não edite o VHost manualmente.

## A stack faz automaticamente

- garante `*.scheduler.argws.com.br` na Cloudflare em DNS-only;
- usa o `CLOUDFLARE_API_TOKEN` no ACME DNS-01;
- cria/remove `_acme-challenge.scheduler.argws.com.br`;
- emite e renova `scheduler.argws.com.br` + `*.scheduler.argws.com.br`;
- aguarda o Reverse Proxy existir no CloudPanel;
- adiciona `*.scheduler.argws.com.br` ao `server_name` do VHost;
- valida com `nginx -t` e faz rollback se necessário;
- instala e renova o certificado via `clpctl site:install:certificate`;
- recarrega o NGINX;
- preserva o header `Host` para o TenantResolver.

## Serviços auxiliares

```text
scheduler-acme
scheduler-cloudpanel-agent
```

O `scheduler-cloudpanel-agent` é o único serviço root-equivalent ao VPS. Ele usa `privileged: true`, `pid: host`, `network_mode: host` e o filesystem do host montado em `/host`; não publica portas nem expõe endpoint. Os demais serviços permanecem sem esse privilégio.

## Verificação

```bash
docker compose --env-file .env -f compose.argws.yaml ps scheduler-acme scheduler-cloudpanel-agent
```

Depois teste:

```text
https://tenant.scheduler.argws.com.br
```

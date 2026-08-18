# Scheduler Pro — deployment Docker ARGWS

O deployment canônico do Scheduler Pro não depende de `clpctl`, NGINX do CloudPanel nem scripts root no host para provisionar tenants ou certificados.

## Arquitetura

```text
Internet
  -> DNS Cloudflare (DNS-only)
  -> scheduler-edge (Traefik em Docker :80/:443)
  -> scheduler-proxy (Docker)
  -> API / Web / Admin
```

O `scheduler-edge` emite e renova automaticamente um único certificado Let's Encrypt via DNS-01 para:

```text
scheduler.argws.com.br
*.scheduler.argws.com.br
```

Esse wildcard cobre automaticamente `admin`, `api`, `proxy` e todos os tenants de um nível sob `scheduler.argws.com.br`. Nenhum tenant exige novo reverse proxy ou novo certificado.

## Subir a stack com edge Docker

```bash
docker compose --env-file .env \
  -f compose.argws.yaml \
  -f compose.docker-edge.yaml \
  pull

docker compose --env-file .env \
  -f compose.argws.yaml \
  -f compose.docker-edge.yaml \
  up -d --remove-orphans
```

O overlay `compose.docker-edge.yaml` adiciona o Traefik à mesma rede Docker e roteia o wildcard para `scheduler-proxy:80`.

## DNS e Let's Encrypt

Use no `.env`:

```env
TLS_PROVISIONING_MODE=local_acme
CLOUDFLARE_TEMPORARY_RECORD_PROXIED=false
LOCAL_ACME_DOMAIN=scheduler.argws.com.br
LOCAL_ACME_PROBE_HOST=scheduler-edge
LOCAL_ACME_PROBE_PORT=443
TRAEFIK_IMAGE=traefik:v3.7
EDGE_BIND_HOST=0.0.0.0
EDGE_HTTP_PORT=80
EDGE_HTTPS_PORT=443
ACME_EMAIL=admin@scheduler.argws.com.br
ACME_CA_SERVER=https://acme-v02.api.letsencrypt.org/directory
```

O token Cloudflare precisa de acesso à zone para leitura e edição DNS. O Traefik usa esse token somente para criar/remover os TXT do challenge DNS-01. Os CNAMEs dos tenants permanecem DNS-only; o Scheduler Pro os reconcilia periodicamente.

## Restrição de portas

No mesmo endereço IP, apenas um processo pode possuir as portas públicas 80/443. Para que o certificado do Traefik seja apresentado diretamente ao navegador, `scheduler-edge` precisa receber essas portas.

Se outro software já ocupa 80/443 no mesmo IP, há somente duas alternativas tecnicamente corretas sem colocar esse software no caminho do Scheduler Pro:

- usar outro IP público já disponível e configurar `EDGE_BIND_HOST` para esse IP; ou
- liberar 80/443 desse IP para o edge Docker.

Não existe forma de dois terminadores TLS independentes compartilharem a mesma combinação IP:443 sem um proxy frontal comum.

## Provisionamento dos tenants

Depois que o edge Docker está de pé, todo tenant novo é automático:

1. cria banco/role isolado;
2. executa migrations;
3. cria storage;
4. cria administrador;
5. cria `tenant.scheduler.argws.com.br -> proxy.scheduler.argws.com.br` em DNS-only;
6. usa imediatamente o wildcard já administrado pelo Traefik;
7. ativa o tenant.

Não há criação manual de site, reverse proxy ou SSL por cliente.

## SMTP

O SMTP é usado para recuperação de senha, teste de entrega e e-mail de boas-vindas. Configure `SMTP_*` no `.env`; não versione credenciais reais.

## Diagnóstico TLS

A API não monta nem lê a chave privada do Traefik. O diagnóstico `local_acme` abre uma conexão TLS interna contra `scheduler-edge:443` usando SNI de `scheduler.argws.com.br` e inspeciona apenas o certificado público apresentado.

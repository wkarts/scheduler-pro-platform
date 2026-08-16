# Scheduler Pro — CloudPanel, Cloudflare e artefatos

Este é o procedimento operacional de urgência para subir a plataforma em `scheduler.argws.com.br`, usando CloudPanel/Docker, Cloudflare e porta interna única `18080`.

## 1. Topologia

Todo tráfego público entra pela Cloudflare e chega no mesmo servidor. No servidor, o CloudPanel aponta todos os domínios do Scheduler Pro para o mesmo proxy Docker:

```text
Internet/Cloudflare
  -> IP público do servidor
  -> CloudPanel/Nginx
  -> http://127.0.0.1:18080
  -> scheduler-proxy container
  -> scheduler-web / scheduler-admin / scheduler-api por Host header
```

## 2. Domínios padrão

```text
scheduler.argws.com.br                WebApp/PWA principal
admin.scheduler.argws.com.br          Admin/Control Plane
api.scheduler.argws.com.br            API pública/control plane
proxy.scheduler.argws.com.br          alvo CNAME interno para tenants/custom hostnames
<codigo-curto>.scheduler.argws.com.br tenant automático gerado pelo provisionamento
```

O código curto do cliente é gerado no backend como `<prefixo>-<hash8>`, por exemplo `barbearia-do-joao-a1b2c3d4`, evitando colisão entre empresas com nomes parecidos.

## 3. DNS no Cloudflare

Crie ou deixe o sistema criar registros equivalentes:

```text
A      scheduler                     <IP_PUBLICO_DO_SERVIDOR>   Proxied
A      admin.scheduler               <IP_PUBLICO_DO_SERVIDOR>   Proxied
A      api.scheduler                 <IP_PUBLICO_DO_SERVIDOR>   Proxied
A      proxy.scheduler               <IP_PUBLICO_DO_SERVIDOR>   Proxied
CNAME  *.scheduler                   proxy.scheduler.argws.com.br Proxied
```

Também é possível não usar wildcard e deixar o Scheduler Pro criar cada subdomínio `<codigo-curto>.scheduler.argws.com.br` pela API Cloudflare. O código usa `CLOUDFLARE_TEMPORARY_RECORD_TYPE=CNAME` e `CLOUDFLARE_TEMPORARY_RECORD_TARGET=proxy.scheduler.argws.com.br`.

Para domínio próprio do cliente, ele deve criar um CNAME para:

```text
proxy.scheduler.argws.com.br
```

Depois disso o Control Plane chama Cloudflare for SaaS / Custom Hostname para validar e emitir SSL.

## 4. CloudPanel

No CloudPanel, crie um site/reverse proxy para cada domínio principal ou um vhost equivalente apontando para:

```text
http://127.0.0.1:18080
```

Domínios mínimos no CloudPanel:

```text
scheduler.argws.com.br
admin.scheduler.argws.com.br
api.scheduler.argws.com.br
```

Para subdomínios automáticos, mantenha Cloudflare proxied e use wildcard DNS. O roteamento real é feito pela aplicação por Host header.

## 5. Deploy Docker

No servidor:

```bash
mkdir -p /opt/scheduler-pro
cd /opt/scheduler-pro
# copie deployments/cloudpanel/compose.yaml como compose.yaml
# copie deployments/cloudpanel/.env.example como .env e preencha segredos

docker compose pull
docker compose up -d
```

A stack publica apenas:

```text
127.0.0.1:18080 -> scheduler-proxy:80
```

Não exponha PostgreSQL, Redis, RabbitMQ ou MinIO publicamente.

## 6. Variáveis críticas

```env
PUBLIC_PLATFORM_DOMAIN=scheduler.argws.com.br
PUBLIC_BASE_URL=https://scheduler.argws.com.br
ADMIN_PLATFORM_DOMAINS=admin.scheduler.argws.com.br,api.scheduler.argws.com.br
TENANT_DEFAULT_DOMAIN_ROOT=scheduler.argws.com.br
APP_BIND_HOST=127.0.0.1
APP_PORT=18080

CLOUDFLARE_API_BASE_URL=https://api.cloudflare.com/client/v4
CLOUDFLARE_API_TOKEN=<token-da-conta>
CLOUDFLARE_ZONE_ID=<zone-id-de-argws>
CLOUDFLARE_DRY_RUN=false
CLOUDFLARE_CUSTOM_HOSTNAME_ORIGIN=proxy.scheduler.argws.com.br
CLOUDFLARE_TEMPORARY_RECORD_TYPE=CNAME
CLOUDFLARE_TEMPORARY_RECORD_TARGET=proxy.scheduler.argws.com.br
```

Não versionar `CLOUDFLARE_API_TOKEN`, `APP_SECRET_KEY`, senhas de banco, RabbitMQ e MinIO.

## 7. Artefatos

A release automática gera e anexa:

```text
scheduler-pro-web-<tag>.tar.gz
scheduler-pro-admin-<tag>.tar.gz
scheduler-pro-cloudpanel-<tag>.tar.gz
scheduler-pro-dockge-<tag>.tar.gz
scheduler-pro-source-<tag>.tar.gz
scheduler-pro-desktop-linux-<tag>.tar.gz
scheduler-pro-desktop-windows-<tag>.tar.gz
scheduler-pro-desktop-macos-<tag>.tar.gz
scheduler-pro-android-*.apk
scheduler-pro-android-*.aab
scheduler-pro-ios-arm64-<tag>-unsigned.ipa
SHA256SUMS.txt / .sha256
```

O APK de debug é instalável para teste. O AAB e o IPA não assinado precisam de assinatura posterior para distribuição formal nas lojas ou instalação em aparelho físico iOS.

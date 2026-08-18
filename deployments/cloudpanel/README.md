# Scheduler Pro no CloudPanel

Este diretório segue o padrão de implantação validado para stacks Docker gerenciadas pelo CloudPanel.

## 1. Preparar arquivos

```bash
mkdir -p /home/scheduler-pro
cd /home/scheduler-pro
cp .env.example .env
```

Edite `.env` e configure domínio, senhas, Cloudflare, WhatsApp e o SMTP transacional.

Para o ambiente ARGWS, confirme especialmente:

```env
PLATFORM_ADMIN_EMAIL=wallace.almeida@wwsoftwares.com.br
PLATFORM_ADMIN_PASSWORD=COLOQUE_AQUI_UMA_SENHA_FORTE_COM_12_OU_MAIS_CARACTERES

PASSWORD_RESET_TTL_MINUTES=30
PASSWORD_RESET_MIN_LENGTH=12

SMTP_HOST=smtp.seu-dominio.com.br
SMTP_PORT=587
SMTP_USERNAME=seu_usuario_smtp
SMTP_PASSWORD=sua_senha_smtp
SMTP_FROM_EMAIL=no-reply@seu-dominio.com.br
SMTP_FROM_NAME=Scheduler Pro
SMTP_REPLY_TO=suporte@seu-dominio.com.br
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=15

# A imagem oficial PostgreSQL cria POSTGRES_USER como superusuário no primeiro initdb.
POSTGRES_USER=scheduler
POSTGRES_PASSWORD=COLOQUE_AQUI_A_SENHA_DO_POSTGRES
POSTGRES_ADMIN_USER=scheduler
POSTGRES_ADMIN_PASSWORD=COLOQUE_AQUI_A_MESMA_SENHA_DO_POSTGRES

# TLS local gerenciado pelo próprio host/CloudPanel.
TLS_PROVISIONING_MODE=local_acme
CLOUDFLARE_TEMPORARY_RECORD_PROXIED=false
LOCAL_ACME_DOMAIN=scheduler.argws.com.br
LOCAL_ACME_CERT_DIR=/run/scheduler-pro-certs
ACME_EMAIL=admin@scheduler.argws.com.br
ACME_DOMAIN=scheduler.argws.com.br
ACME_STAGING=false
ACME_DNS_SLEEP=20
```

Nunca versione a senha administrativa ou credenciais SMTP/PostgreSQL/Cloudflare reais. Elas devem existir somente no `.env` do servidor/secret store.

O SMTP é usado para recuperação de senha, teste de entrega e e-mail de boas-vindas ao administrador de um tenant provisionado. Se `SMTP_HOST`/`SMTP_FROM_EMAIL` não estiverem configurados, a recuperação retorna `SMTP_NOT_CONFIGURED` em vez de simular envio.

## 2. Subir stack

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d
```

As variáveis de autenticação/reset/SMTP/TLS são propagadas pelo bloco comum de ambiente para migration/bootstrap, API e workers. O diretório `${SCHEDULER_PRO_DATA_ROOT}/certs` é montado read-only na API e no worker de provisionamento para diagnóstico; a chave privada permanece root-only no host.

## 3. TLS local ACME/Let's Encrypt no CloudPanel

O modo padrão ARGWS é `TLS_PROVISIONING_MODE=local_acme`. Ele evita depender de **Cloudflare SSL for SaaS / Custom Hostnames**, inclusive em contas que retornam o erro Cloudflare `1404 No quota has been allocated`.

A arquitetura fica:

```text
Internet
  -> DNS Cloudflare (DNS-only para *.scheduler.argws.com.br)
  -> CloudPanel / NGINX :443
  -> certificado Let's Encrypt local
     scheduler.argws.com.br + *.scheduler.argws.com.br
  -> reverse proxy http://127.0.0.1:18080
  -> scheduler-proxy -> API/Web/Admin
```

O wildcard cobre automaticamente, sem emissão por tenant:

- `scheduler.argws.com.br`;
- `admin.scheduler.argws.com.br`;
- `api.scheduler.argws.com.br`;
- `proxy.scheduler.argws.com.br`;
- qualquer tenant `tenant.scheduler.argws.com.br`.

### 3.1 Permissões do token Cloudflare

Para este modo o token é usado **somente para DNS**. Use escopos equivalentes a:

- Zone / Zone / Read;
- Zone / DNS / Edit;
- recurso limitado à zone `argws.com.br`.

Não é necessário contratar `SSL and Certificates Read/Write` ou Cloudflare for SaaS para os hostnames sob `*.scheduler.argws.com.br`.

### 3.2 Emitir e instalar o wildcard

Execute uma vez no host CloudPanel, como root:

```bash
cd /home/scheduler-pro/deployments/cloudpanel
bash scripts/install-local-acme-cloudpanel.sh .env
```

O instalador:

1. instala `acme.sh` no host se necessário;
2. emite `scheduler.argws.com.br` + `*.scheduler.argws.com.br` via Let's Encrypt ACME v2 e Cloudflare DNS-01;
3. grava a cópia operacional em `${SCHEDULER_PRO_DATA_ROOT}/certs`;
4. instala o certificado no site CloudPanel usando `clpctl site:install:certificate`;
5. adiciona `*.scheduler.argws.com.br` ao `server_name` do VHost do site, com backup e `nginx -t` antes do reload;
6. mantém o `reloadcmd` no acme.sh para que toda renovação seja reinstalada automaticamente no CloudPanel.

O acme.sh instala um cron diário de renovação. Não use diretamente os certificados internos de `~/.acme.sh`; a cópia em `${SCHEDULER_PRO_DATA_ROOT}/certs` é mantida por `--install-cert`.

### 3.3 DNS dos tenants

Em `local_acme`, os CNAMEs dos tenants precisam ser **DNS-only**. O Scheduler Pro reconcilia:

```text
tenant.scheduler.argws.com.br CNAME proxy.scheduler.argws.com.br
proxied = false
```

Se um registro antigo estiver laranja/proxied, use **Domínios e SSL -> Verificar** após o deploy. A reconciliação o converte para DNS-only. Se o proxy Cloudflare continuar ligado, o navegador verá o certificado do edge Cloudflare e não o wildcard local.

### 3.4 Diagnóstico

Em **Integrações**, o Control Plane passa a mostrar `local_acme` com:

- presença do `fullchain.pem`;
- presença da chave privada sem ler/expor seu conteúdo;
- SANs do certificado;
- data de expiração;
- dias restantes;
- confirmação de instalação no CloudPanel;
- estado final `READY`, `INCOMPLETE` ou `MISSING_CERTIFICATE`.

## 4. Domínios próprios externos

Um domínio como `agenda.cliente.com.br` não é coberto por `*.scheduler.argws.com.br`.

No modo `local_acme`, o backend **não chama Cloudflare Custom Hostnames** para hostnames gerenciados da plataforma. Domínios externos ficam `PENDING_VALIDATION` e são identificados como `custom_domain_local_acme`, aguardando provisionamento ACME próprio no host. Instalações que realmente contrataram Cloudflare SSL for SaaS podem usar `TLS_PROVISIONING_MODE=cloudflare_saas` como fallback.

## 5. CloudPanel

Crie ou mantenha o site reverse proxy `scheduler.argws.com.br` apontando para:

```text
http://127.0.0.1:18080
```

O proxy interno roteia:

- `/api/*` para FastAPI;
- `admin.*` ou `/admin/` para Super Admin;
- demais hosts para webapp tenant PWA.

O arquivo `compose.acme.yaml` permanece como emissor container legado/opcional. Para CloudPanel, o provisionador **canônico** é `scripts/install-local-acme-cloudpanel.sh`, porque somente o host consegue executar `clpctl` e recarregar corretamente o NGINX que ocupa a porta 443.

## 6. Atualização

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --remove-orphans
```

Após alterar a configuração TLS, rode novamente:

```bash
bash scripts/install-local-acme-cloudpanel.sh .env
```

## 7. Recuperar provisionamento estagnado

O provisionamento é idempotente por passo. Passos marcados como `completed` não são repetidos em um retry; somente passos ainda pendentes, em execução ou que falharam são reenfileirados.

O runtime faz `rollback` da sessão antes de persistir uma falha, impedindo que um erro PostgreSQL deixe o job indefinidamente em `RUNNING/PROVISIONING`. Jobs `FAILED` podem ser reenfileirados imediatamente. Jobs `PENDING/PROVISIONING` só podem ser reprocessados quando estiverem sem atualização por pelo menos 10 minutos, evitando execução concorrente do mesmo job.

No Control Plane, abra **Provisionamento** e use **Tentar novamente** ou **Reprocessar** no job existente. Não crie outro tenant apenas para recuperar uma execução interrompida: banco, migrations, storage, DNS, administrador e demais passos já concluídos são preservados.

Após `ActivateTenant`, o tenant, o domínio validado e `tenant_resource_boundaries.isolation_status` devem convergir para `ACTIVE`; somente então o login pelo hostname do tenant é liberado.

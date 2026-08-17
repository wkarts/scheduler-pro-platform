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
```

Nunca versione a senha administrativa ou as credenciais SMTP reais. Elas devem existir somente no `.env` do servidor/secret store.

O SMTP é usado para recuperação de senha, teste de entrega e e-mail de boas-vindas ao administrador de um tenant provisionado. Se `SMTP_HOST`/`SMTP_FROM_EMAIL` não estiverem configurados, a recuperação retorna `SMTP_NOT_CONFIGURED` em vez de simular envio.

## 2. Subir stack

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d
```

As variáveis de autenticação/reset/SMTP são propagadas pelo bloco comum de ambiente para migration/bootstrap, API e workers.

## 3. CloudPanel

Crie um site reverse proxy apontando para:

```text
http://127.0.0.1:18080
```

Use HTTPS no CloudPanel/Cloudflare. O proxy interno roteia:

- `/api/*` para FastAPI;
- `admin.*` ou `/admin/` para Super Admin;
- demais hosts para webapp tenant PWA.

O perfil `compose.acme.yaml` permanece opcional e não precisa ser iniciado no ambiente ARGWS enquanto CloudPanel/Cloudflare forem responsáveis pela terminação TLS.

## 4. Atualização

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --remove-orphans
```

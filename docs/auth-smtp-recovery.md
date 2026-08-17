# Scheduler Pro — SMTP, recuperação de senha e onboarding

## Variáveis

```env
PLATFORM_ADMIN_EMAIL=admin@seu-dominio.com.br
PLATFORM_ADMIN_PASSWORD=senha-forte-com-12-ou-mais-caracteres
PASSWORD_RESET_TTL_MINUTES=30
PASSWORD_RESET_MIN_LENGTH=12

SMTP_HOST=smtp.seu-dominio.com.br
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=no-reply@seu-dominio.com.br
SMTP_FROM_NAME=Scheduler Pro
SMTP_REPLY_TO=suporte@seu-dominio.com.br
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=15
```

Use STARTTLS (`SMTP_USE_TLS=true`) ou SSL direto (`SMTP_USE_SSL=true`), nunca os dois simultaneamente.

## Recuperação

- Plataforma: `POST /api/v1/auth/platform/password/forgot` e `POST /api/v1/auth/platform/password/reset`.
- Tenant: `POST /api/v1/auth/password/forgot` e `POST /api/v1/auth/password/reset`.
- A solicitação sempre responde de forma genérica para evitar enumeração de usuários.
- O token é aleatório, de uso único e somente o hash é persistido.
- Um novo pedido invalida tokens pendentes anteriores.
- A troca da senha invalida todas as sessões e refresh tokens do usuário.
- O tempo de vida é controlado por `PASSWORD_RESET_TTL_MINUTES`.

## Onboarding de tenant

Novos provisionamentos incluem `SendWelcomeEmail`. Depois que banco, migrations, storage, DNS, administrador e perfis de build estiverem disponíveis, o runtime tenta enviar ao administrador:

- nome e código do tenant;
- URL HTTPS do tenant;
- e-mail administrativo;
- senha inicial gerada/configurada.

Falha do SMTP é registrada como `tenant_welcome_email_failed`, mas não destrói nem reverte um tenant já provisionado.

## Desktop genérico

O Desktop cliente genérico não deve usar `scheduler.argws.com.br` como se fosse um tenant. Ele solicita o hostname recebido no e-mail de onboarding e monta a API do tenant como `https://<hostname>/api/v1`. Builds dedicados continuam recebendo o endpoint diretamente do Build Profile.

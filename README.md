# Scheduler Pro Platform

Plataforma SaaS multitenant de agendamentos construída com **FastAPI/Python 3.13**, **PostgreSQL**, **Redis**, **RabbitMQ**, **Vue 3 + Tailwind PWA** e **Tauri 2** para desktop/mobile.

O núcleo permanece em Python/FastAPI. Tauri é usado somente para aplicativos clientes da API SaaS.

## Estado funcional

- Fundação de banco/Alembic/bootstrap: **IMPLEMENTED**;
- autenticação, sessões, refresh rotativo e RBAC: **IMPLEMENTED**;
- resolução/isolation multitenant por hostname e banco: **IMPLEMENTED**;
- readiness de PostgreSQL/tenant/Redis/RabbitMQ/MinIO: **IMPLEMENTED**;
- motor completo de agenda/disponibilidade/concorrência: **PARTIAL** — próximo incremento;
- Outbox/notificações/WhatsApp real: **PARTIAL/PLANNED** — incremento posterior;
- Web/Admin operacionais completos: **PARTIAL**;
- provisionamento/Cloudflare real: **PARTIAL/BLOCKED_EXTERNAL quando faltarem credenciais**;
- instaladores Desktop e APK/AAB finais: **PARTIAL** — não considerar fontes/PWA como artefato nativo concluído.

## Estrutura

```text
apps/
  api/        FastAPI + SQLAlchemy Async
  web/        Webapp tenant PWA
  admin/      Control Plane
  desktop/    Tauri 2 Desktop
  mobile/     Tauri 2 Mobile
packages/     contratos e SDK
infrastructure/docker/
deployments/
docs/
```

## Execução local da fundação

```bash
cp .env.example .env
docker compose -f deployments/development/docker-compose.yml up --build -d
```

O serviço `bootstrap` cria/aplica, de forma idempotente, `platform`, `tenant_dev`, migrations, domínios locais, admins/RBAC e bucket MinIO antes de liberar a API.

Ver comandos completos em `docs/operations/DEVELOPMENT.md`.

## Health

```bash
curl -H 'Host: localhost' http://127.0.0.1:8000/api/v1/health/live
curl -H 'Host: localhost' http://127.0.0.1:8000/api/v1/health/ready
```

`/health/live` verifica processo. `/health/ready` verifica as dependências obrigatórias e revisions Alembic; falha retorna HTTP 503.

## Migrations

Platform:

```bash
cd apps/api
alembic -c alembic.ini upgrade head
```

Tenant:

```bash
ALEMBIC_TENANT_DATABASE=tenant_dev \
ALEMBIC_TENANT_USER=tenant_dev_user \
ALEMBIC_TENANT_PASSWORD=tenant_dev_password \
alembic -c alembic-tenant.ini upgrade head
```

Os SQLs históricos foram preservados como baseline; não houve reconstrução destrutiva.

## CI

Pipelines relevantes da fundação:

- `CI`: compile, lint, typecheck, unit tests, frontend build e Docker image builds;
- `Integration Tests`: Compose real, bootstrap, readiness, PostgreSQL multitenant, Redis, RabbitMQ, MinIO, auth/RBAC/isolation e round-trip Alembic.

## Imagens GHCR

A infraestrutura existente continua preparada para:

```text
ghcr.io/wkarts/scheduler-pro-platform/python-base:latest
ghcr.io/wkarts/scheduler-pro-platform/api:latest
ghcr.io/wkarts/scheduler-pro-platform/worker:latest
ghcr.io/wkarts/scheduler-pro-platform/web:latest
ghcr.io/wkarts/scheduler-pro-platform/admin:latest
ghcr.io/wkarts/scheduler-pro-platform/proxy:latest
```

## Segurança

Nenhum segredo real deve ser commitado. `tenant_databases.password_ref` contém somente uma referência (`secret://...`) resolvida antes da conexão. Em produção, utilize secrets/secret manager e chave de aplicação forte.

Detalhes: `docs/security/SECURITY.md`, `docs/architecture/AUTHORIZATION.md` e `docs/architecture/MULTITENANCY.md`.

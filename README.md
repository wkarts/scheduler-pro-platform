# Scheduler Pro Platform

Plataforma SaaS multitenant de agendamentos construída com **FastAPI/Python 3.13**, **PostgreSQL**, **Redis**, **RabbitMQ** e **Vue 3 + Tailwind PWA**. A experiência principal é **PWA-first**; Tauri 2 permanece ativo somente para os aplicativos mobile Android/iOS.

O código desktop legado continua preservado para eventual retomada, mas não participa dos workflows, releases ou validações obrigatórias atuais.

## Estado funcional auditado

- Fundação de banco/Alembic/bootstrap: **IMPLEMENTED** neste incremento.
- Autenticação, sessões, refresh rotativo e RBAC: **IMPLEMENTED** neste incremento.
- Resolução/isolamento multitenant por hostname e banco: **IMPLEMENTED** neste incremento.
- Readiness de PostgreSQL/tenant/Redis/RabbitMQ/MinIO: **IMPLEMENTED** neste incremento.
- Motor completo de agenda/disponibilidade/concorrência: **PARTIAL** — próximo incremento.
- Outbox/notificações/WhatsApp real: **PARTIAL/PLANNED** — incremento posterior.
- Web/Admin operacionais completos: **PARTIAL**.
- Provisionamento/Cloudflare real: **PARTIAL**; operações externas ficam `BLOCKED_EXTERNAL` quando faltarem credenciais.
- PWA cliente/admin: **ATIVO e prioritário**.
- Mobile nativo: **ATIVO** para Android/APK e iOS/IPA.
- Desktop Windows/Linux/macOS: **PRESERVADO COMO LEGADO**, fora do fluxo de build/release atual.

## Estrutura

```text
apps/
  api/        FastAPI + SQLAlchemy Async
  web/        Webapp tenant PWA instalável
  admin/      Super Admin / Control Plane PWA instalável
  desktop/    Tauri 2 Desktop legado (fora do pipeline ativo)
  mobile/     Tauri 2 Mobile ativo
packages/     contratos e SDK
infrastructure/docker
  base/python Imagem base Python 3.13
  api         Imagem API
  worker      Imagem workers Celery
  web         Imagem web/admin PWA via Nginx
  proxy       Reverse proxy interno
deployments/
  development
  cloudpanel
  dockge
docs/
```

## Imagens GHCR

```text
ghcr.io/wkarts/scheduler-pro-platform/python-base:latest
ghcr.io/wkarts/scheduler-pro-platform/api:latest
ghcr.io/wkarts/scheduler-pro-platform/worker:latest
ghcr.io/wkarts/scheduler-pro-platform/web:latest
ghcr.io/wkarts/scheduler-pro-platform/admin:latest
ghcr.io/wkarts/scheduler-pro-platform/proxy:latest
```

A imagem `python-base` evita recompilar dependências nativas em toda build da API/worker.

## Execução local

```bash
cp .env.example .env
docker compose -f deployments/development/docker-compose.yml up --build
```

O serviço `bootstrap` cria/aplica de forma idempotente `tenant_dev`, migrations platform/tenant, domínios locais, administradores/RBAC e bucket MinIO antes de liberar a API.

Health checks:

```bash
curl -H 'Host: localhost' http://127.0.0.1:8000/api/v1/health/live
curl -H 'Host: localhost' http://127.0.0.1:8000/api/v1/health/ready
```

`/health/live` verifica o processo. `/health/ready` verifica dependências obrigatórias e revisions Alembic e retorna HTTP 503 quando a fundação não está pronta.

Comandos detalhados: `docs/operations/DEVELOPMENT.md`.

## CloudPanel/Dockge

Use os pacotes em:

```text
deployments/cloudpanel
deployments/dockge
```

Exemplo:

```bash
cd deployments/cloudpanel
cp .env.example .env
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d
```

No CloudPanel, aponte o reverse proxy para:

```text
http://127.0.0.1:18080
```

## Builds e artefatos

Workflows existentes:

- `CI`: valida API, frontend e Docker; neste incremento ganhou compile/lint/typecheck/testes unitários mais rigorosos.
- `Integration Tests`: valida Compose, bootstrap, PostgreSQL multitenant, Redis, RabbitMQ, MinIO, autenticação/RBAC, readiness e round-trip Alembic.
- `Base Image`: publica `python-base`.
- `Images`: publica `api`, `worker`, `web`, `admin`, `proxy` e `python-base`.
- `Release`: publica PWA/deploy e, quando executado, artefatos mobile Android/APK e iOS/IPA; não gera desktop.
- `Mobile Artifacts`: gera os artefatos nativos mobile.
- `Desktop Artifacts`: retirado do fluxo ativo e preservado somente em `docs/legacy-workflows/desktop-artifacts.yml.disabled`.

## Validação local

```bash
bash scripts/validate-local.sh
bash scripts/build/build-images-local.sh local
bash scripts/build/package-web-artifacts.sh local
```

A validação integral da fundação também pode ser executada pela stack de desenvolvimento:

```bash
docker compose -f deployments/development/docker-compose.yml up --build -d
docker compose -f deployments/development/docker-compose.yml exec -T api pytest -q -m integration
```

## Segurança

Nenhum segredo deve ser commitado. Use `.env`, GitHub Actions Secrets e secret manager em produção.

`tenant_databases.password_ref` armazena somente uma referência (`secret://...`); a senha é resolvida pelo `SecretResolver` antes da abertura da conexão.

Detalhes: `docs/security/SECURITY.md`, `docs/architecture/AUTHORIZATION.md` e `docs/architecture/MULTITENANCY.md`.

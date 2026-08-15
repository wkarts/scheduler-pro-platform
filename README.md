# Scheduler Pro Platform

Plataforma SaaS multitenant de agendamentos construída com **FastAPI/Python**, **PostgreSQL**, **Redis**, **RabbitMQ**, **Vue 3 + Tailwind PWA** e **Tauri 2** para desktop/mobile.

Este repositório segue o contrato técnico do projeto: Control Plane, Tenant Plane e Delivery Plane. O núcleo permanece em Python/FastAPI. Tauri é usado somente para os aplicativos gerenciais desktop e mobile.

## Estrutura

```text
apps/
  api/        FastAPI + SQLAlchemy Async + Alembic-ready
  web/        Webapp tenant PWA instalável
  admin/      Super Admin / Control Plane PWA instalável
  desktop/    Tauri 2 Desktop
  mobile/     Tauri 2 Mobile
backend/      domínio compartilhado futuro
services/     serviços assíncronos e workers
packages/     contratos, SDK e componentes compartilhados
infrastructure/docker
deployments/development
docs/
```

## Fundamentos implementados

- Tenant resolvido por hostname, nunca por `tenant_id` arbitrário do frontend.
- Control Plane separado do Tenant Plane.
- Banco da plataforma e banco individual por tenant.
- Provisionamento idempotente por steps.
- Agenda com proteção contra double booking no PostgreSQL.
- Landing Page Builder com versionamento.
- WhatsApp API com provider abstrato.
- Webhooks idempotentes.
- Transactional Outbox.
- RBAC e feature flags.
- Web/admin como PWA instalável pelo navegador.
- Desktop/mobile com Tauri 2 consumindo a API.

## Execução local

```bash
cp .env.example .env
docker compose -f deployments/development/docker-compose.yml up --build
```

API:

```text
http://localhost:8000
```

Web tenant:

```text
http://localhost:5173
```

Admin:

```text
http://localhost:5174
```

## Validação

```bash
bash scripts/validate-local.sh
```

## Segurança

Nenhum segredo deve ser commitado. Use `.env`, secrets do GitHub Actions e secret manager em produção.

## Status

Branch inicial de foundation pronta para evolução incremental por PRs: agenda, WhatsApp, landing builder, Cloudflare, build manager e hardening.
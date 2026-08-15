# Scheduler Pro Platform

Plataforma SaaS multitenant de agendamentos construída com **FastAPI/Python**, **PostgreSQL**, **Redis**, **RabbitMQ**, **Vue 3 + Tailwind PWA** e **Tauri 2** para desktop/mobile.

O núcleo permanece em Python/FastAPI. Tauri é usado somente para os aplicativos gerenciais desktop e mobile.

## Estrutura

```text
apps/
  api/        FastAPI + SQLAlchemy Async
  web/        Webapp tenant PWA instalável
  admin/      Super Admin / Control Plane PWA instalável
  desktop/    Tauri 2 Desktop
  mobile/     Tauri 2 Mobile
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

Workflows disponíveis:

- `CI`: valida API, frontend e Docker.
- `Base Image`: publica `python-base`.
- `Images`: publica `api`, `worker`, `web`, `admin`, `proxy` e `python-base`.
- `Release`: publica imagens e anexa artefatos web/admin/deploy em tag `v*.*.*`.
- `Desktop Artifacts`: gera Tauri desktop unsigned para Windows/Linux/macOS.
- `Mobile Artifacts`: gera PWA mobile e build Android unsigned quando habilitado.

## Validação local

```bash
bash scripts/validate-local.sh
bash scripts/build/build-images-local.sh local
bash scripts/build/package-web-artifacts.sh local
```

## Segurança

Nenhum segredo deve ser commitado. Use `.env`, GitHub Actions Secrets e secret manager em produção.

# Entrega, imagens base e distribuição

O Scheduler Pro possui distribuição separada por serviço para evitar rebuilds desnecessários e facilitar rollback.

## Imagem base

```text
ghcr.io/wkarts/scheduler-pro-platform/python-base:latest
```

A base contém Python 3.13, dependências nativas, `libpq-dev`, `curl`, timezone e usuário não-root. API e workers herdam essa base.

## Imagens publicadas

```text
ghcr.io/wkarts/scheduler-pro-platform/api:<tag>
ghcr.io/wkarts/scheduler-pro-platform/worker:<tag>
ghcr.io/wkarts/scheduler-pro-platform/web:<tag>
ghcr.io/wkarts/scheduler-pro-platform/admin:<tag>
ghcr.io/wkarts/scheduler-pro-platform/proxy:<tag>
ghcr.io/wkarts/scheduler-pro-platform/python-base:<tag>
```

## CloudPanel/Dockge

Use:

```text
deployments/cloudpanel/compose.yaml
deployments/dockge/compose.yaml
```

As stacks incluem `pull_policy: always`, healthchecks, volumes persistentes, storage-init, Redis, RabbitMQ, MinIO, PostgreSQL, workers e proxy.

## Artefatos

O workflow `Release` gera:

- `scheduler-pro-web-<tag>.tar.gz`;
- `scheduler-pro-admin-<tag>.tar.gz`;
- `scheduler-pro-cloudpanel-deploy-<tag>.tar.gz`;
- `scheduler-pro-dockge-deploy-<tag>.tar.gz`.

O workflow `Desktop Artifacts` gera Tauri desktop unsigned para Windows, Linux e macOS.

O workflow `Mobile Artifacts` gera pacote PWA instalável e, quando habilitado, build Android unsigned.

## Comandos locais

```bash
bash scripts/build/build-images-local.sh local
bash scripts/build/package-web-artifacts.sh local
bash scripts/deploy/cloudpanel-up.sh
```

# Entrega, imagens base e distribuição

O Scheduler Pro possui distribuição separada por serviço para evitar rebuilds desnecessários e facilitar rollback. A estratégia atual é **PWA-first**.

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

O workflow `Release` gera os pacotes de PWA/deploy e pode anexar os artefatos mobile ativos:

- Web/PWA tenant;
- Admin/PWA;
- Android APK;
- iOS IPA.

Desktop Windows/Linux/macOS não é publicado. O workflow antigo está preservado apenas como referência em `docs/legacy-workflows/desktop-artifacts.yml.disabled`.

> O uso de runner `macos` no job iOS é requisito de compilação do IPA e não habilita uma release desktop macOS.

## Comandos locais

```bash
bash scripts/build/build-images-local.sh local
bash scripts/build/package-web-artifacts.sh local
bash scripts/deploy/cloudpanel-up.sh
```

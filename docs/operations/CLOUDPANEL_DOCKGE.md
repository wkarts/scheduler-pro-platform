# CloudPanel / Dockge

## Fluxo recomendado

1. Publicar imagens pelo workflow `Images` ou por tag `v*.*.*`.
2. Copiar `deployments/cloudpanel` ou `deployments/dockge` para o servidor.
3. Criar `.env` a partir de `.env.example`.
4. Fazer login no GHCR se o package estiver privado:

```bash
echo SEU_TOKEN_GITHUB | docker login ghcr.io -u SEU_USUARIO --password-stdin
```

5. Subir a stack:

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --remove-orphans
```

## Reverse proxy

CloudPanel deve apontar para:

```text
http://127.0.0.1:18080
```

O container `scheduler-proxy` roteia API, web tenant e admin.

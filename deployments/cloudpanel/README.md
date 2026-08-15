# Scheduler Pro no CloudPanel

Este diretório segue o padrão de implantação validado para stacks Docker gerenciadas pelo CloudPanel.

## 1. Preparar arquivos

```bash
mkdir -p /home/scheduler-pro
cd /home/scheduler-pro
cp .env.example .env
```

Edite `.env` e configure domínio, senhas, Cloudflare e WhatsApp.

## 2. Subir stack

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d
```

## 3. CloudPanel

Crie um site reverse proxy apontando para:

```text
http://127.0.0.1:18080
```

Use HTTPS no CloudPanel/Cloudflare. O proxy interno roteia:

- `/api/*` para FastAPI;
- `admin.*` ou `/admin/` para Super Admin;
- demais hosts para webapp tenant PWA.

## 4. Atualização

```bash
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --remove-orphans
```

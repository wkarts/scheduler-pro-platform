# API

Prefixo oficial:

```text
/api/v1
```

Padrão de sucesso:

```json
{"data": {}, "meta": {}}
```

Padrão de erro:

```json
{"error": {"code": "APPOINTMENT_SLOT_UNAVAILABLE", "message": "Horário não disponível.", "details": {}}}
```

Tags OpenAPI planejadas:

- Authentication
- Customers
- Appointments
- Services
- Professionals
- Landing Pages
- WhatsApp
- Files
- Branding
- Build Manager
- Platform

## Branding / White-label

```text
GET  /api/v1/branding/manifest
PUT  /api/v1/branding/profile
POST /api/v1/branding/publish
POST /api/v1/branding/build-profiles
```

O manifesto de branding é resolvido pelo hostname do tenant. O frontend não recebe autoridade por `tenant_id` arbitrário.

## Build Manager

```text
GET  /api/v1/platform/builds/profiles
POST /api/v1/platform/builds/requests
GET  /api/v1/platform/builds/jobs
GET  /api/v1/platform/builds/jobs/{job_id}
POST /api/v1/platform/builds/jobs/{job_id}/artifacts
```

O Build Manager registra `build_requests`, `build_jobs`, `build_logs`, `build_artifacts` e `build_credentials`. Os workflows GitHub Actions são o executor inicial, e a plataforma mantém o estado e o catálogo dos artefatos.

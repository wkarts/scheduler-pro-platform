# Deploy ARGWS no CloudPanel

Este guia é o caminho operacional canônico para homologação urgente do Scheduler Pro em `scheduler.argws.com.br`.

## 1. DNS Cloudflare

Todos os registros apontam para o mesmo servidor. O CloudPanel encaminha para `127.0.0.1:18080` e o `scheduler-proxy` roteia por hostname.

```text
A      scheduler         SEU_IP_PUBLICO   proxied
A      admin.scheduler   SEU_IP_PUBLICO   proxied
A      api.scheduler     SEU_IP_PUBLICO   proxied
A      proxy.scheduler   SEU_IP_PUBLICO   proxied
CNAME  *.scheduler       proxy.scheduler.argws.com.br   proxied
```

Domínio próprio do cliente:

```text
agenda.cliente.com.br CNAME proxy.scheduler.argws.com.br
```

Depois cadastre o domínio no Admin para o Scheduler Pro chamar Cloudflare Custom Hostnames e acompanhar validação/SSL.

## 2. CloudPanel

Crie um site/reverse proxy para cada domínio principal, todos apontando para:

```text
http://127.0.0.1:18080
```

Domínios do site:

```text
scheduler.argws.com.br
admin.scheduler.argws.com.br
api.scheduler.argws.com.br
*.scheduler.argws.com.br
```

## 3. Compose recomendado

Use:

```bash
cp deployments/cloudpanel/.env.example .env
cp deployments/cloudpanel/rabbitmq.conf .
docker compose -f deployments/cloudpanel/compose.argws.yaml pull
docker compose -f deployments/cloudpanel/compose.argws.yaml up -d --remove-orphans
```

O arquivo `compose.argws.yaml` já contém:

- bootstrap do usuário `PLATFORM_ADMIN_EMAIL`;
- API e workers com variáveis Cloudflare/Evolution;
- RabbitMQ 4 com compatibilidade para Celery;
- workers sem `mingle/gossip/heartbeat` para não criar filas temporárias deprecated;
- proxy único em `127.0.0.1:18080`.

## 4. Login administrativo

Configure no `.env`:

```env
PLATFORM_ADMIN_EMAIL=admin@scheduler.argws.com.br
PLATFORM_ADMIN_PASSWORD=troque-por-uma-senha-admin-forte
```

O serviço `scheduler-migrate` executa:

```bash
python -m app.cli migrate-platform
python -m app.bootstrap platform-admin
```

## 5. Checagem

```bash
docker compose -f deployments/cloudpanel/compose.argws.yaml ps
docker compose -f deployments/cloudpanel/compose.argws.yaml logs -f scheduler-api scheduler-worker-default scheduler-worker-whatsapp scheduler-rabbitmq
curl -H 'Host: scheduler.argws.com.br' http://127.0.0.1:18080/api/v1/health/ready
```

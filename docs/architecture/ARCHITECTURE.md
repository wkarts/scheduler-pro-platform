# Arquitetura Scheduler Pro

A plataforma é dividida em três planos:

## Control Plane

Gerencia tenants, planos, assinaturas, domínios, provisionamento, integrações, builds, feature flags, auditoria global e configurações da plataforma.

## Tenant Plane

Executa a operação de cada empresa: clientes, profissionais, serviços, agenda, landing pages, WhatsApp, notificações, arquivos, branding, relatórios e configurações.

Cada tenant possui banco próprio e usuário PostgreSQL próprio. O backend nunca aceita `tenant_id` vindo arbitrariamente do frontend como autoridade de acesso.

## Delivery Plane

Entrega infraestrutura: Docker, Nginx/CloudPanel, Cloudflare, DNS, SSL, Celery, RabbitMQ, Redis, MinIO/S3, backups e observabilidade.

## Stack

- Python 3.13
- FastAPI
- SQLAlchemy Async
- PostgreSQL
- Redis
- RabbitMQ/Celery
- MinIO/S3
- Vue 3 + Tailwind
- PWA para web/admin
- Tauri 2 para desktop/mobile

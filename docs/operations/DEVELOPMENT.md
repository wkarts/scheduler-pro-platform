# Scheduler Pro — Desenvolvimento

## Subir a fundação completa

A partir da raiz do repositório:

```bash
docker compose -f deployments/development/docker-compose.yml up --build -d
```

O serviço `bootstrap` é obrigatório e idempotente. Ele:

1. cria o usuário PostgreSQL de `tenant_dev`;
2. cria o banco `tenant_dev` quando ausente;
3. aplica Alembic no banco `platform`;
4. registra tenant, bancos, storage e domínios de desenvolvimento;
5. aplica Alembic em `tenant_dev`;
6. cria o administrador tenant e RBAC mínimo;
7. cria o superadministrador de plataforma;
8. cria o bucket MinIO privado de desenvolvimento.

A API somente inicia depois do bootstrap concluir com código zero.

## Credenciais exclusivamente de desenvolvimento

Os valores presentes em `.env.example` são seeds locais e não devem ser reutilizados em produção. Em produção, `APP_SECRET_KEY` fraco/placeholder é rejeitado durante a carga de configuração.

O banco tenant nunca recebe `password_ref` como senha literal. O registro armazena uma referência como:

```text
secret://env/TENANT_DEV_DATABASE_PASSWORD
```

`EnvSecretResolver` resolve a referência no momento da criação da engine.

## Health checks

```bash
curl -H 'Host: localhost' http://127.0.0.1:8000/api/v1/health/live
curl -H 'Host: localhost' http://127.0.0.1:8000/api/v1/health/ready
```

`live` valida apenas o processo. `ready` valida PostgreSQL platform + revision Alembic, tenant + revision Alembic, Redis, RabbitMQ e MinIO/S3. Falha obrigatória resulta em HTTP 503.

## Migrations

Platform:

```bash
cd apps/api
alembic -c alembic.ini current
alembic -c alembic.ini upgrade head
```

Tenant de desenvolvimento:

```bash
cd apps/api
ALEMBIC_TENANT_DATABASE=tenant_dev \
ALEMBIC_TENANT_USER=tenant_dev_user \
ALEMBIC_TENANT_PASSWORD=tenant_dev_password \
alembic -c alembic-tenant.ini current
```

Os SQLs históricos não foram apagados. Eles foram incorporados como revisões baseline para preservar bancos existentes.

## Testes

Testes sem infraestrutura:

```bash
cd apps/api
pytest -q -m 'not integration'
```

Validação integral igual ao CI:

```bash
docker compose -f deployments/development/docker-compose.yml up --build -d
docker compose -f deployments/development/docker-compose.yml exec -T api pytest -q -m integration
```

## Encerrar e limpar dados locais

```bash
docker compose -f deployments/development/docker-compose.yml down
```

Para remover também os volumes de desenvolvimento, apenas quando a perda dos dados locais for intencional:

```bash
docker compose -f deployments/development/docker-compose.yml down -v
```

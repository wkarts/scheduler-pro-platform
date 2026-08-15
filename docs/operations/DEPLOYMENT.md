# Deploy

## Desenvolvimento

```bash
cp .env.example .env
docker compose -f deployments/development/docker-compose.yml up --build
```

## Produção

CloudPanel, Portainer e Dockge podem gerenciar os containers, mas não são dependências do domínio da aplicação.

Checklist mínimo:

- Definir secrets reais fora do repositório.
- Configurar PostgreSQL com usuário administrador separado de usuários tenant.
- Habilitar HTTPS Full Strict na Cloudflare.
- Configurar backups de platform DB, tenants DBs e storage.
- Executar migrations controladas.
- Habilitar logs JSON e métricas.

# Multitenancy — Scheduler Pro

## Status

**IMPLEMENTED no incremento de fundação:** resolução do tenant por hostname, validação de tenant/domínio ativo, isolamento por banco PostgreSQL, resolução de segredo da credencial e cache controlado de engines.

## Autoridade do tenant

O `tenant_id` enviado pelo frontend não é autoridade de acesso. A autoridade é o hostname normalizado da requisição.

Fluxo:

1. o hostname é normalizado;
2. `X-Forwarded-Host` somente é aceito quando a conexão vem de proxy listado em `TRUSTED_PROXY_HOSTS`;
3. o control plane consulta `domains`, `tenants`, `tenant_databases` e `tenant_storage`;
4. domínio deve estar `ACTIVE`;
5. tenant deve estar `ACTIVE`;
6. a referência de senha é resolvida pelo `SecretResolver`;
7. a sessão é aberta no banco dedicado do tenant.

Em produção não existe fallback automático para `dev-tenant`. O fallback para `localhost`/`127.0.0.1` é permitido somente com `APP_ENV=development`.

## Isolamento de dados

Cada tenant utiliza banco PostgreSQL próprio. O access token contém o tenant resolvido no login, mas esse valor não substitui a autoridade do hostname: a dependência de autenticação compara o tenant autenticado com o tenant resolvido da requisição.

Um token emitido no tenant A e reutilizado no hostname do tenant B recebe `TENANT_CONTEXT_MISMATCH`.

Os testes de integração criam um segundo banco PostgreSQL (`tenant_test_b`) e provam que clientes gravados no tenant A não aparecem no tenant B e vice-versa.

## Credenciais de banco

`tenant_databases.password_ref` armazena somente uma referência, por exemplo:

```text
secret://env/TENANT_DEV_DATABASE_PASSWORD
```

A referência não pode ser utilizada como senha literal. No desenvolvimento, `EnvSecretResolver` resolve o valor. A interface `SecretResolver` permite adicionar Vault, AWS Secrets Manager ou Docker Secrets sem alterar o domínio de tenant.

## Cache de engines

A chave de cache considera:

- hostname;
- host/porta PostgreSQL;
- database;
- database_user;
- credential_version.

O cache possui limite, TTL/LRU, lock assíncrono, invalidação explícita e `engine.dispose()` na expulsão/encerramento.

## Estados rejeitados

- hostname ausente/desconhecido: `TENANT_NOT_FOUND`;
- domínio diferente de `ACTIVE`: `DOMAIN_NOT_ACTIVE`;
- tenant `SUSPENDED`: `TENANT_SUSPENDED`;
- demais estados não ativos: `TENANT_NOT_ACTIVE`.

## Próximas fases

**PLANNED:** provisionamento real de novos bancos/segredos/domínios, Cloudflare Custom Hostnames e rotação externa de credenciais. Esses itens não fazem parte do primeiro incremento.

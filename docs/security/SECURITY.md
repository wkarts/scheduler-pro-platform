# Segurança — Scheduler Pro

## Estado da fundação

A fundação atual implementa controles mínimos obrigatórios para autenticação, autorização, multitenancy e segredos. Este documento não declara como concluídas integrações ou hardening de fases posteriores.

## Senhas

- senhas de usuário são verificadas com Argon2 via Passlib;
- senha em texto puro não é persistida;
- o fluxo de login usa hash dummy para reduzir diferenças óbvias de tempo entre usuário inexistente e senha inválida;
- contas podem ser temporariamente bloqueadas após tentativas inválidas.

## Tokens

- access token: JWT HS256 de curta duração no estado atual;
- refresh token: valor opaco aleatório;
- somente SHA-256 do refresh token é persistido;
- refresh é rotativo;
- reutilização de refresh revogado invalida a sessão;
- sessão persistida é consultada em cada requisição privada.

## Segredos

`password_ref` é uma referência, nunca a senha do banco. O resolver de desenvolvimento aceita apenas `secret://env/<NOME>`.

`APP_SECRET_KEY` placeholder/fraco é rejeitado fora de `APP_ENV=development`.

Nunca registrar em logs:

- senha;
- access token;
- refresh token;
- chave S3;
- segredo de integração;
- conteúdo resolvido pelo `SecretResolver`.

## Hostname e proxy

O tenant é determinado pelo hostname normalizado. `X-Forwarded-Host` somente pode substituir `Host` quando o cliente direto está em `TRUSTED_PROXY_HOSTS`.

Domínio não ativo e tenant não ativo/suspenso são rejeitados antes da sessão tenant.

## Desenvolvimento

As credenciais em `.env.example` são exclusivamente seeds locais e deliberadamente identificáveis como desenvolvimento. Não podem ser reutilizadas em produção.

## CI

O CI da fundação executa:

- `compileall`;
- Ruff;
- mypy estrito no núcleo de segurança;
- pytest unitário;
- Docker build;
- stack real com PostgreSQL, Redis, RabbitMQ e MinIO;
- migrations Alembic;
- testes de autenticação/RBAC/isolamento;
- readiness;
- downgrade/upgrade das migrations novas seguido de novo bootstrap e smoke test.

## Pendências futuras

**PLANNED:** MFA, rotação por secret manager externo, HMAC/token de serviço para callbacks internos do Build Manager, rate limiting distribuído e política de headers/CSP do deployment final.

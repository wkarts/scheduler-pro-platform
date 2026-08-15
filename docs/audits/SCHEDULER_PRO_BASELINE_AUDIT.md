# Scheduler Pro — Baseline Audit

**Data da auditoria:** 2026-08-15  
**Repositório:** `wkarts/scheduler-pro-platform`  
**Branch auditada:** `main`  
**SHA auditado:** `54b905c2f683b84f0af0f771a01a30f3588cc9d5`  
**Versão declarada pela API:** `0.1.0-alpha.1`  
**Release mais recente no baseline:** `v0.1.0-alpha.6`

## Estado da referência

A referência remota de `main` foi comparada com o SHA informado para a auditoria. O resultado foi `identical`, com `ahead_by=0` e `behind_by=0`. Portanto não havia commits posteriores a preservar antes do primeiro incremento.

## Ambiente e comandos/evidências

A inspeção foi executada pela API do GitHub e pelos logs do GitHub Actions. Uma tentativa adicional de clone no sandbox de execução falhou por indisponibilidade de resolução DNS para `github.com`; por isso nenhum resultado local foi inventado ou promovido como evidência.

Baseline histórico verificável no GitHub Actions, run `31880058780` (`CI`, run 69):

- `api`: sucesso;
- `web`: sucesso;
- `docker`: sucesso;
- backend executou `compileall` e `pytest -q`;
- resultado dos testes backend do baseline: **3 passed in 0.34s**;
- o job Docker apenas construiu imagens; não subiu a stack nem executou readiness/smoke contra PostgreSQL, Redis, RabbitMQ e MinIO.

## Testes existentes no baseline

1. `test_landing_sanitizer.py`;
2. `test_no_frontend_tenant_authority.py`;
3. `test_response_contract.py`.

Não existiam testes reais para autenticação, refresh, RBAC, sessão, PostgreSQL multitenant, isolamento entre bancos, readiness profundo ou bootstrap Docker.

## Falhas reproduzidas no código

- `/auth/login` emitia access token para qualquer e-mail e senha;
- `/auth/refresh` retornava apenas mensagem de intenção;
- rotas tenant privadas não exigiam usuário autenticado/RBAC;
- rotas de plataforma não exigiam superadministrador;
- `database_password_ref` era passado diretamente como senha ao driver PostgreSQL;
- cache de engines tenant era indexado apenas pelo nome do banco e não possuía TTL/LRU/dispose/invalidação;
- fallback `localhost` de tenant existia sem estar condicionado explicitamente a `APP_ENV=development`;
- Compose inicializava somente `platform` por SQL montado em `docker-entrypoint-initdb.d`;
- `tenant_dev` não era criado;
- migrations tenant, white-label e Build Manager não eram aplicadas automaticamente no desenvolvimento;
- não havia `alembic_version` funcional;
- `/health/ready` retornava `ready: true` sem consultar dependências;
- CI backend não usava PostgreSQL/Redis/RabbitMQ/MinIO reais;
- CI Docker não executava a stack nem smoke test.

## Serviços e artefatos

O baseline continha definições para PostgreSQL, Redis, RabbitMQ, MinIO e API. A definição, porém, não possuía bootstrap integral de tenant nem validação ponta a ponta no CI.

A release `v0.1.0-alpha.6` foi publicada para o SHA auditado. Entre os assets auditados aparecem `scheduler-pro-desktop-source-v0.1.0-alpha.6.tar.gz` e `scheduler-pro-mobile-source-v0.1.0-alpha.6.tar.gz`. Esses nomes e conteúdos de distribuição declarados representam fontes empacotadas, não evidência de instalador Desktop ou APK final. Essa dívida permanece fora do primeiro incremento e deve ser tratada na fase de Build Manager/artefatos.

## Riscos críticos do baseline

1. acesso não autenticado ou com credenciais inválidas;
2. ausência de revogação/rotação de sessão;
3. violação de isolamento por rotas sem RBAC;
4. uso incorreto de referência de segredo como credencial;
5. ambiente de desenvolvimento não reproduzível;
6. readiness falso-positivo;
7. CI verde sem validar a infraestrutura necessária à aplicação.

## Classificação após auditoria

- Autenticação: **PARTIAL / INSEGURO**;
- Autorização: **PLANNED**;
- Alembic: **PLANNED**;
- bootstrap local: **PARTIAL**;
- multitenancy por hostname: **PARTIAL**;
- readiness: **STUB**;
- integração PostgreSQL no CI: **PLANNED**;
- artefatos Desktop/Mobile finais: **PLANNED**.

Este documento registra o baseline e não é reescrito para refletir artificialmente o estado posterior às correções.

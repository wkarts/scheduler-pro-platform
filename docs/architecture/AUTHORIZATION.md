# Autenticação e Autorização — Scheduler Pro

## Status

**IMPLEMENTED no incremento de fundação:** login real, Argon2, sessões persistentes, access token curto, refresh token opaco/rotativo, revogação, detecção de reutilização e RBAC persistente.

## Tipos de usuário

- `PlatformUser`: usuário do control plane. Rotas de plataforma exigem superadministrador no escopo atual.
- `TenantUser`: usuário operacional mantido dentro do banco do tenant.

## Login tenant

O login:

1. resolve hostname/tenant;
2. localiza usuário no banco tenant;
3. valida `is_active` e bloqueio temporário;
4. valida senha Argon2;
5. carrega roles e permissions persistidas;
6. cria `user_sessions`;
7. cria refresh token aleatório e persiste somente SHA-256;
8. emite access JWT com `sid`, `tenant_id` e tipo de usuário;
9. registra auditoria.

Falhas de e-mail inexistente e senha incorreta retornam a mesma resposta para reduzir enumeração de usuários. Tentativas inválidas incrementam contador e podem bloquear temporariamente a conta.

## Refresh e revogação

Refresh tokens são rotativos. Após uso:

- o token anterior é revogado;
- um substituto é emitido;
- reutilização de token revogado revoga a sessão inteira;
- logout revoga sessão e refresh tokens associados;
- logout-all revoga todas as sessões do usuário.

## RBAC

As permissões do token não são tratadas como fonte definitiva. Em cada requisição autenticada, a sessão e as permissões são recarregadas do banco, permitindo revogação operacional sem aguardar expiração do access token.

Permissões seed do tenant administrador:

- `appointments.read`;
- `appointments.create`;
- `appointments.update`;
- `appointments.cancel`;
- `customers.read`;
- `customers.manage`;
- `services.manage`;
- `professionals.manage`;
- `notifications.manage`;
- `whatsapp.manage`;
- `landing_pages.manage`;
- `branding.manage`;
- `reports.read`;
- `tenant.manage`.

Dependências centrais:

- `get_current_user` / `get_current_tenant_user`;
- `get_current_platform_user`;
- `require_permission`;
- `require_role`;
- `require_super_admin`.

## Ainda não concluído

**PLANNED para endurecimento posterior:** recuperação/troca de senha completa, `require_internal_service_token`, MFA e políticas avançadas de sessão. Não são declaradas como implementadas neste incremento.

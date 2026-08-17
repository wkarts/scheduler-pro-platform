# Permissões da gestão de tenant

- Leitura do painel: `tenants.read`.
- Alteração cadastral e administrador principal: `tenants.update`.
- Suspender/restaurar: `tenants.update`.
- Exclusão lógica: `tenants.delete` pelo endpoint canônico já existente.

Superadmins continuam autorizados pelo modelo atual do Control Plane.

# Isolamento da conta administrativa do tenant

O usuário principal do cliente é consultado e atualizado no banco isolado do próprio tenant. A
operação do Control Plane apenas orquestra essa alteração e não mistura usuários entre tenants.

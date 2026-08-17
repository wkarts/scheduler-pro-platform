# Rotação da senha principal do tenant

Ao definir uma nova senha pelo Control Plane, o Scheduler PRO:

1. calcula novo hash Argon2;
2. atualiza somente o usuário principal no banco isolado do tenant;
3. zera tentativas/lock de login;
4. revoga sessões e refresh tokens anteriores;
5. atualiza a referência secreta usada pelo provisionamento idempotente.

A senha em texto não é retornada pela API após a atualização.

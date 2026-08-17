# Segurança da gestão do tenant

A troca de credencial do administrador principal ocorre no banco isolado do tenant. O endpoint não
retorna a senha, utiliza Argon2 para o hash e revoga sessões/refresh tokens anteriores quando há
rotação de senha.

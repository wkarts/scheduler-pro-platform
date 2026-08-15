# Provisionamento

O provisionamento é assíncrono e idempotente.

Steps oficiais:

1. CreateTenant
2. CreateDatabase
3. RunMigrations
4. CreateStorage
5. CreateTemporaryDomain
6. ConfigureCloudflare
7. CreateAdmin
8. SeedTenant
9. ActivateTenant

Cada step possui status `pending`, `running`, `completed` ou `failed`. Uma falha pode ser retomada sem recriar recursos já existentes.

# Gestão administrativa do tenant

O Control Plane expõe a gestão operacional do tenant diretamente no Admin.

## Onde fica

Após autenticar no painel administrativo, use o botão flutuante **Gerenciar tenant**.

O painel permite:

- selecionar qualquer tenant visível ao perfil administrativo;
- editar nome e fuso horário;
- consultar código/slug e domínio principal;
- alterar e-mail e nome do administrador principal do tenant;
- trocar a senha do administrador principal;
- revogar automaticamente as sessões antigas quando a senha é trocada;
- suspender e restaurar o tenant;
- excluir logicamente o tenant, preservando banco, storage e artefatos.

O código/slug não é editável depois do provisionamento porque participa dos identificadores de banco,
storage, domínios e perfis de distribuição. Alterá-lo diretamente quebraria o isolamento e os vínculos
de infraestrutura.

## API

```http
GET /api/v1/platform/tenant-management/{tenant_id}
PUT /api/v1/platform/tenant-management/{tenant_id}
PUT /api/v1/platform/tenant-management/{tenant_id}/principal-admin
```

A exclusão lógica e o ciclo de vida continuam usando os endpoints canônicos:

```http
POST   /api/v1/platform/tenants/{tenant_id}/suspend
POST   /api/v1/platform/tenants/{tenant_id}/restore
DELETE /api/v1/platform/tenants/{tenant_id}
```

A conta principal é alterada diretamente no banco isolado do tenant. A senha nunca é retornada pelo
endpoint; quando rotacionada, apenas o novo hash é persistido e as sessões existentes são revogadas.

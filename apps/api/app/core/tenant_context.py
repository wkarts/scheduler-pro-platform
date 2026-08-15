from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str
    slug: str
    database: str
    database_user: str
    database_password_ref: str
    storage_bucket: str
    hostname: str
    timezone: str = "America/Bahia"

    def assert_same_tenant(self, authenticated_tenant_id: str | None) -> None:
        if authenticated_tenant_id and authenticated_tenant_id != self.tenant_id:
            from app.core.errors import APIError
            raise APIError("TENANT_CONTEXT_MISMATCH", "Usuário autenticado não pertence ao tenant resolvido.", 403)

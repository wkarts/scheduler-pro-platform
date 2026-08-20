from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.db.session import tenant_session
from app.services.observability_service import ObservabilityService
from app.services.tenant_access_resend_service import TenantAccessResendService
from app.services.tenant_management_service import TenantManagementService
from app.services.tenant_resolver import TenantResolver

router = APIRouter()


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)

    @model_validator(mode="after")
    def require_change(self) -> "TenantUpdateRequest":
        if self.name is None and self.timezone is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class TenantPrincipalAdminUpdateRequest(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    password: str | None = Field(default=None, min_length=12, max_length=128)

    @model_validator(mode="after")
    def require_change(self) -> "TenantPrincipalAdminUpdateRequest":
        if self.email is None and self.display_name is None and self.password is None:
            raise ValueError("Informe e-mail, nome ou nova senha.")
        return self


class TenantAccessResendRequest(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    generate_password: bool = False

    @model_validator(mode="after")
    def validate_password_mode(self) -> "TenantAccessResendRequest":
        if self.password is not None and self.generate_password:
            raise ValueError("Informe uma nova senha ou gere uma senha temporária, não ambos.")
        return self


@router.get("/{tenant_id}")
async def tenant_management_snapshot(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await TenantManagementService(session).snapshot(tenant_id))


@router.get("/{tenant_id}/logs")
async def tenant_management_logs(
    tenant_id: str,
    source: str | None = Query(default=None),
    service: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    principal: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    """Return the consolidated operational history for one administered tenant.

    Platform-bound events are always attempted first. Tenant-database events are
    appended when the isolated database is reachable, so a tenant DB outage does
    not hide the Control Plane history that is most useful during an incident.
    """

    assert_platform_tenant_access(principal, tenant_id)
    platform_rows = await ObservabilityService(session).list_platform_logs(
        tenant_filter=tenant_id,
        source=source,
        service=service,
        level=level,
        integration=integration,
        search=search,
        limit=limit,
    )
    rows: list[dict[str, Any]] = [{**row, "scope": "platform"} for row in platform_rows]

    try:
        context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
        async for tenant_db in tenant_session(context):
            tenant_rows = await ObservabilityService(tenant_db).list_tenant_logs(
                source=source,
                service=service,
                level=level,
                integration=integration,
                search=search,
                limit=limit,
            )
            rows.extend({**row, "scope": "tenant"} for row in tenant_rows)
            break
    except Exception as exc:  # noqa: BLE001 - diagnostics must degrade gracefully
        rows.append(
            {
                "id": f"diagnostic-{tenant_id}",
                "source": "control-plane",
                "service": "tenant-management",
                "level": "WARNING",
                "event": "tenant_log_source_unavailable",
                "message": "O banco isolado do tenant não pôde ser consultado; exibindo o histórico disponível no Control Plane.",
                "details": {"error_type": type(exc).__name__},
                "scope": "platform",
                "created_at": None,
            }
        )

    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return success(rows[:limit])


@router.put("/{tenant_id}")
async def update_tenant_management(
    tenant_id: str,
    payload: TenantUpdateRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantManagementService(session).update_tenant(
            tenant_id,
            name=payload.name,
            timezone=payload.timezone,
            actor=principal.email,
        )
    )


@router.put("/{tenant_id}/principal-admin")
async def update_tenant_principal_admin(
    tenant_id: str,
    payload: TenantPrincipalAdminUpdateRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantManagementService(session).update_principal_admin(
            tenant_id,
            email=str(payload.email) if payload.email is not None else None,
            display_name=payload.display_name,
            password=payload.password,
            actor=principal.email,
        )
    )


@router.post("/{tenant_id}/principal-admin/resend-access")
async def resend_tenant_principal_admin_access(
    tenant_id: str,
    payload: TenantAccessResendRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantAccessResendService(session).resend(
            tenant_id,
            email=str(payload.email) if payload.email is not None else None,
            display_name=payload.display_name,
            password=payload.password,
            generate_password=payload.generate_password,
            actor=principal.email,
        )
    )

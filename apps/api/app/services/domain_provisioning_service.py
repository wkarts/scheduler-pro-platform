from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.db.models_platform import Domain, Tenant
from app.services.cloudflare_service import CloudflareService


class DomainProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cloudflare = CloudflareService(
            settings.cloudflare_api_token,
            settings.cloudflare_zone_id,
            api_base_url=settings.cloudflare_api_base_url,
            dry_run=settings.cloudflare_dry_run,
            custom_hostname_origin=settings.cloudflare_custom_hostname_origin,
        )

    async def _tenant(self, tenant_id: str) -> Tenant:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            raise APIError("TENANT_NOT_FOUND", "Cliente/tenant não encontrado.", 404)
        return tenant

    async def _domain_by_id(self, domain_id: str) -> Domain:
        domain = await self.session.get(Domain, domain_id)
        if domain is None:
            raise APIError("DOMAIN_NOT_FOUND", "Domínio não encontrado.", 404)
        return domain

    async def _domain_by_hostname(self, hostname: str) -> Domain | None:
        return (
            await self.session.execute(select(Domain).where(Domain.hostname == hostname.lower()))
        ).scalar_one_or_none()

    async def create_temporary_domain(self, tenant_id: str) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        hostname = f"{tenant.slug}.{settings.tenant_domain_root}".lower()
        domain = await self._domain_by_hostname(hostname)
        if domain is None:
            domain = Domain(
                tenant_id=tenant.id,
                hostname=hostname,
                is_primary=True,
                is_temporary=True,
                status="CONFIGURING",
                validation={},
            )
            self.session.add(domain)
            await self.session.flush()
        result = await self.cloudflare.create_dns_record(
            hostname,
            settings.tenant_domain_target,
            record_type=settings.cloudflare_temporary_record_type,
            proxied=True,
        )
        domain.status = "ACTIVE" if result.get("dry_run") else "CONFIGURING"
        domain.validation = {"mode": "temporary", "cloudflare": result}
        await self.session.commit()
        return self.serialize(domain)

    async def connect_custom_domain(
        self,
        tenant_id: str,
        hostname: str,
        *,
        make_primary: bool = False,
    ) -> dict[str, Any]:
        await self._tenant(tenant_id)
        clean_hostname = hostname.strip().lower().rstrip(".")
        domain = await self._domain_by_hostname(clean_hostname)
        if domain is None:
            domain = Domain(
                tenant_id=tenant_id,
                hostname=clean_hostname,
                is_primary=make_primary,
                is_temporary=False,
                status="PENDING_VALIDATION",
                validation={},
            )
            self.session.add(domain)
            await self.session.flush()
        result = await self.cloudflare.create_custom_hostname(clean_hostname)
        cf_result = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
        domain.validation = {
            "mode": "custom_hostname",
            "cloudflare": result,
            "custom_hostname_id": cf_result.get("id"),
            "validation_records": cf_result.get("validation_records"),
        }
        domain.status = "PENDING_VALIDATION"
        if result.get("dry_run"):
            domain.status = "ACTIVE"
        if make_primary:
            await self.session.execute(
                update(Domain)
                .where(Domain.tenant_id == tenant_id)
                .values(is_primary=False)
            )
            domain.is_primary = True
        await self.session.commit()
        return self.serialize(domain)

    async def check_domain(self, domain_id: str) -> dict[str, Any]:
        domain = await self._domain_by_id(domain_id)
        hostname_id = domain.validation.get("custom_hostname_id") if domain.validation else None
        if hostname_id:
            result = await self.cloudflare.get_custom_hostname_status(str(hostname_id))
        else:
            result = await self.cloudflare.get_validation_status(domain.hostname)
        cf_result = result.get("result", {}) if isinstance(result.get("result"), dict) else {}
        ssl_status = cf_result.get("ssl", {}).get("status") if isinstance(cf_result.get("ssl"), dict) else None
        if result.get("dry_run") or cf_result.get("status") == "active" or ssl_status == "active":
            domain.status = "ACTIVE"
        else:
            domain.status = "PENDING_VALIDATION"
        domain.validation = {**(domain.validation or {}), "last_check": result}
        await self.session.commit()
        return self.serialize(domain)

    async def purge_domain_cache(self, domain_id: str) -> dict[str, Any]:
        domain = await self._domain_by_id(domain_id)
        result = await self.cloudflare.purge_cache(domain.hostname)
        domain.validation = {**(domain.validation or {}), "last_cache_purge": result}
        await self.session.commit()
        return {"domain": self.serialize(domain), "purge": result}

    @staticmethod
    def serialize(domain: Domain) -> dict[str, Any]:
        return {
            "id": str(domain.id),
            "tenant_id": str(domain.tenant_id),
            "hostname": domain.hostname,
            "is_primary": domain.is_primary,
            "is_temporary": domain.is_temporary,
            "status": domain.status,
            "validation": domain.validation,
        }

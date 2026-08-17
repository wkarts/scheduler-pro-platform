from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.db.models_platform import Domain, Tenant
from app.services.cloudflare_service import CloudflareService
from app.services.observability_service import ObservabilityService


class DomainProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cloudflare = CloudflareService(
            settings.cloudflare_api_token,
            settings.cloudflare_zone_id,
            api_base_url=settings.cloudflare_api_base_url,
            dry_run=settings.cloudflare_dry_run,
            custom_hostname_origin=settings.cloudflare_custom_hostname_origin,
            zone_name_hint=settings.cloudflare_zone_name,
            custom_hostname_ca=settings.cloudflare_custom_hostname_ca,
        )
        self.logs = ObservabilityService(session)

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
            await self.session.execute(
                select(Domain).where(Domain.hostname == hostname.lower())
            )
        ).scalar_one_or_none()

    @staticmethod
    def _assert_domain_owner(domain: Domain, tenant_id: str) -> None:
        if str(domain.tenant_id) != str(tenant_id):
            raise APIError(
                "TENANT_DOMAIN_CONFLICT",
                "O domínio informado já pertence a outro cliente/tenant.",
                409,
                {"hostname": domain.hostname},
            )

    async def _record_cloudflare_failure(
        self,
        *,
        tenant_id: str | None,
        event: str,
        message: str,
        error: Exception,
        hostname: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details: dict[str, Any] = {
            "exception": error.__class__.__name__,
            "message": str(error),
        }
        if isinstance(error, APIError):
            error_details.update(
                {
                    "code": error.code,
                    "status_code": error.status_code,
                    "details": error.details,
                }
            )
        if details:
            error_details.update(details)
        await self.logs.record_platform_log(
            tenant_id=tenant_id,
            source="integration",
            service="cloudflare",
            level="ERROR",
            event=event,
            message=message,
            integration="cloudflare",
            error_code=getattr(error, "code", "CLOUDFLARE_FAILURE"),
            hostname=hostname,
            details=error_details,
        )

    async def _mark_temporary_dns_active(
        self,
        domain: Domain,
        dns_result: dict[str, Any],
    ) -> None:
        domain.status = "ACTIVE"
        domain.validation = {
            **(domain.validation or {}),
            "mode": "temporary_dns",
            "record_exists": True,
            "target": settings.tenant_domain_target,
            "dns": dns_result,
            "integration_status": "HEALTHY",
        }

    @staticmethod
    def _preserve_last_known_domain_state(
        domain: Domain,
        *,
        mode: str,
        error_key: str,
        error: APIError,
        record_exists: bool | None = None,
    ) -> bool:
        """Persist a remote integration failure without destroying last-known-good state.

        Cloudflare can reject a later check/purge while the DNS record or custom
        hostname already exists. In that situation the local domain must stay ACTIVE
        and the integration is marked DEGRADED instead of fabricating a DNS outage.
        """

        previous = dict(domain.validation or {})
        was_active = str(domain.status).upper() == "ACTIVE"
        domain.status = "ACTIVE" if was_active else "PENDING_VALIDATION"
        validation: dict[str, Any] = {
            **previous,
            "mode": mode,
            "integration_status": "DEGRADED" if was_active else "UNVERIFIED",
            error_key: {
                "code": error.code,
                "message": error.message,
                "status_code": error.status_code,
                "details": error.details,
            },
        }
        if record_exists is not None:
            validation["record_exists"] = (
                True if was_active and previous.get("record_exists") is True else record_exists
            )
        domain.validation = validation
        return was_active

    async def create_temporary_domain(self, tenant_id: str) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        hostname = f"{tenant.slug}.{settings.tenant_domain_root}".lower()
        domain = await self._domain_by_hostname(hostname)
        if domain is not None:
            self._assert_domain_owner(domain, str(tenant.id))
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
        try:
            result = await self.cloudflare.ensure_dns_record(
                hostname,
                settings.tenant_domain_target,
                record_type=settings.cloudflare_temporary_record_type,
                proxied=True,
            )
            await self._mark_temporary_dns_active(domain, result)
        except APIError as exc:
            self._preserve_last_known_domain_state(
                domain,
                mode="temporary_dns",
                error_key="cloudflare_error",
                error=exc,
                record_exists=False,
            )
            await self._record_cloudflare_failure(
                tenant_id=str(tenant.id),
                event="temporary_domain_dns_failed",
                message="Falha ao criar ou confirmar DNS temporário na Cloudflare.",
                error=exc,
                hostname=hostname,
            )
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
        if domain is not None:
            self._assert_domain_owner(domain, tenant_id)
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
        try:
            result = await self.cloudflare.ensure_custom_hostname(clean_hostname)
            cf_result = (
                result.get("result", {})
                if isinstance(result.get("result"), dict)
                else {}
            )
            raw_ssl = cf_result.get("ssl")
            ssl_data: dict[str, Any] = raw_ssl if isinstance(raw_ssl, dict) else {}
            domain.validation = {
                "mode": "custom_hostname",
                "cloudflare": result,
                "custom_hostname_id": cf_result.get("id"),
                "validation_records": ssl_data.get("validation_records") or cf_result.get("validation_records"),
                "certificate_authority": ssl_data.get("certificate_authority") or settings.cloudflare_custom_hostname_ca,
                "integration_status": "HEALTHY",
            }
            domain.status = (
                "ACTIVE"
                if result.get("dry_run")
                or str(cf_result.get("status") or "").lower() == "active"
                or str(ssl_data.get("status") or "").lower() == "active"
                else "PENDING_VALIDATION"
            )
        except APIError as exc:
            self._preserve_last_known_domain_state(
                domain,
                mode="custom_hostname",
                error_key="cloudflare_error",
                error=exc,
            )
            await self._record_cloudflare_failure(
                tenant_id=tenant_id,
                event="custom_hostname_failed",
                message="Falha ao registrar hostname customizado na Cloudflare.",
                error=exc,
                hostname=clean_hostname,
            )
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
        try:
            if domain.is_temporary:
                result = await self.cloudflare.ensure_dns_record(
                    domain.hostname,
                    settings.tenant_domain_target,
                    record_type=settings.cloudflare_temporary_record_type,
                    proxied=True,
                )
                await self._mark_temporary_dns_active(
                    domain,
                    {**result, "check": True},
                )
            else:
                hostname_id = (
                    domain.validation.get("custom_hostname_id")
                    if domain.validation
                    else None
                )
                if hostname_id:
                    result = await self.cloudflare.get_custom_hostname_status(
                        str(hostname_id)
                    )
                else:
                    result = await self.cloudflare.ensure_custom_hostname(domain.hostname)
                cf_result = (
                    result.get("result", {})
                    if isinstance(result.get("result"), dict)
                    else {}
                )
                raw_ssl = cf_result.get("ssl")
                ssl_data: dict[str, Any] = raw_ssl if isinstance(raw_ssl, dict) else {}
                ssl_status = ssl_data.get("status")
                if (
                    result.get("dry_run")
                    or cf_result.get("status") == "active"
                    or ssl_status == "active"
                ):
                    domain.status = "ACTIVE"
                else:
                    domain.status = "PENDING_VALIDATION"
                domain.validation = {
                    **(domain.validation or {}),
                    "custom_hostname_id": cf_result.get("id")
                    or (domain.validation or {}).get("custom_hostname_id"),
                    "validation_records": ssl_data.get("validation_records")
                    or cf_result.get("validation_records"),
                    "last_check": result,
                    "integration_status": "HEALTHY",
                }
        except APIError as exc:
            previous_validation = dict(domain.validation or {})
            mode = str(
                previous_validation.get("mode")
                or ("temporary_dns" if domain.is_temporary else "custom_hostname")
            )
            self._preserve_last_known_domain_state(
                domain,
                mode=mode,
                error_key="last_check_error",
                error=exc,
            )
            await self._record_cloudflare_failure(
                tenant_id=str(domain.tenant_id),
                event="domain_check_failed",
                message="Falha ao verificar domínio na Cloudflare.",
                error=exc,
                hostname=domain.hostname,
            )
        await self.session.commit()
        return self.serialize(domain)

    async def purge_domain_cache(self, domain_id: str) -> dict[str, Any]:
        domain = await self._domain_by_id(domain_id)
        try:
            result = await self.cloudflare.purge_cache(domain.hostname)
            domain.validation = {
                **(domain.validation or {}),
                "last_cache_purge": result,
            }
            await self.session.commit()
            return {"domain": self.serialize(domain), "purge": result}
        except APIError as exc:
            failure = {
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            }
            domain.validation = {
                **(domain.validation or {}),
                "last_cache_purge_error": failure,
            }
            await self._record_cloudflare_failure(
                tenant_id=str(domain.tenant_id),
                event="domain_cache_purge_failed",
                message="Falha no purge de cache Cloudflare.",
                error=exc,
                hostname=domain.hostname,
            )
            await self.session.commit()
            raise

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

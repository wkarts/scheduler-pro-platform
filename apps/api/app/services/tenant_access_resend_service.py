from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.mail_service import mail_delivery
from app.services.observability_service import ObservabilityService
from app.services.tenant_management_service import TenantManagementService


class TenantAccessResendService:
    """Atualiza e reenvia o acesso principal de um tenant pelo Control Plane.

    A senha atual do usuário nunca é recuperada. Quando o operador deseja enviar
    uma senha, ele deve informar uma nova senha ou solicitar uma senha temporária.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.management = TenantManagementService(session)
        self.logs = ObservabilityService(session)

    @staticmethod
    def generate_temporary_password() -> str:
        # 24+ caracteres, sem depender de estado externo.
        return secrets.token_urlsafe(18)

    async def resend(
        self,
        tenant_id: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
        password: str | None = None,
        generate_password: bool = False,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if password and generate_password:
            raise APIError(
                "TENANT_ACCESS_PASSWORD_CONFLICT",
                "Informe uma nova senha ou peça para gerar uma senha temporária, não ambos.",
                422,
            )

        temporary_password = self.generate_temporary_password() if generate_password else password
        if temporary_password and len(temporary_password) < 12:
            raise APIError(
                "TENANT_ACCESS_PASSWORD_TOO_SHORT",
                "A nova senha deve ter no mínimo 12 caracteres.",
                422,
            )

        before = await self.management.snapshot(tenant_id)
        admin_before = before.get("principal_admin") or {}
        target_email = str(email or admin_before.get("email") or "").strip().lower()
        if not target_email:
            raise APIError(
                "TENANT_ACCESS_RECIPIENT_REQUIRED",
                "O administrador principal do tenant não possui e-mail para receber o acesso.",
                409,
            )

        changed = bool(
            temporary_password
            or (email and str(email).strip().lower() != str(admin_before.get("email") or "").lower())
            or (display_name and str(display_name).strip() != str(admin_before.get("display_name") or ""))
        )
        if changed:
            snapshot = await self.management.update_principal_admin(
                tenant_id,
                email=target_email,
                display_name=display_name,
                password=temporary_password,
                actor=actor,
            )
        else:
            snapshot = before

        tenant = snapshot["tenant"]
        recipient = str((snapshot.get("principal_admin") or {}).get("email") or target_email)
        hostname = str(tenant.get("primary_hostname") or "").strip()
        if not hostname:
            raise APIError(
                "TENANT_ACCESS_HOSTNAME_UNAVAILABLE",
                "O tenant ainda não possui domínio disponível para reenviar o acesso.",
                409,
            )
        login_url = f"https://{hostname}/"

        # O método de boas-vindas já usa o SMTP oficial da plataforma. Quando a
        # senha não foi redefinida, enviamos explicitamente que a senha atual foi
        # preservada em vez de tentar recuperar um hash ou segredo possivelmente
        # desatualizado.
        password_text = temporary_password or "Sua senha atual permanece a mesma; ela não foi redefinida neste reenvio."
        result = mail_delivery.send_tenant_welcome(
            recipient=recipient,
            tenant_name=str(tenant.get("name") or tenant.get("slug") or "Tenant"),
            tenant_code=str(tenant.get("slug") or ""),
            temporary_password=password_text,
            login_url=login_url,
        )

        await self.logs.record_platform_log(
            tenant_id=tenant_id,
            source="admin",
            service="control-plane",
            event="tenant_access_credentials_resent",
            message=(
                "Dados de acesso reenviados ao administrador principal do tenant."
                if result.delivered
                else "Alterações de acesso salvas, mas o e-mail de reenvio falhou."
            ),
            actor=actor,
            integration="smtp",
            error_code=result.error_code,
            details={
                "recipient": recipient,
                "login_url": login_url,
                "email_changed": target_email != str(admin_before.get("email") or "").lower(),
                "password_rotated": bool(temporary_password),
                "password_generated": bool(generate_password),
                "sessions_revoked": bool(temporary_password),
                "delivered": result.delivered,
                "delivery_message": result.message,
            },
        )
        await self.session.commit()

        return {
            "snapshot": snapshot,
            "delivery": {
                "delivered": result.delivered,
                "error_code": result.error_code,
                "message": result.message,
                "recipient": recipient,
                "login_url": login_url,
            },
            # Exibido apenas uma vez quando o Control Plane gerou a senha. Não é
            # persistido em logs nem devolvido em consultas posteriores.
            "temporary_password": temporary_password if generate_password else None,
        }

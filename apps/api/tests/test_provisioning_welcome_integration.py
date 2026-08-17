import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.core.secrets import seal_secret
from app.db.models_platform import Tenant
from app.db.session import PlatformSession, platform_engine
from app.services.mail_service import MailDeliveryResult, mail_delivery
from app.services.provisioning_runtime import ProvisioningRuntime

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_welcome_email_step_updates_jsonb_without_aborting_transaction(monkeypatch) -> None:
    """Reproduz o caminho que travou SendWelcomeEmail em produção.

    O tenant semeado no ambiente de integração não possui a referência da senha
    inicial porque ele não passa pelo provisionamento SaaS completo. O teste
    injeta as mesmas precondições usadas por CreateTenant/CreateAdmin, simula
    indisponibilidade SMTP e executa o update JSONB real via asyncpg.
    """

    def fake_delivery(**_kwargs) -> MailDeliveryResult:
        return MailDeliveryResult(
            delivered=False,
            error_code="SMTP_TEST_FAILURE",
            message="Falha SMTP simulada pelo teste de integração.",
        )

    monkeypatch.setattr(mail_delivery, "send_tenant_welcome", fake_delivery)

    try:
        async with PlatformSession() as session:
            tenant = (
                await session.execute(
                    select(Tenant).where(Tenant.slug == settings.dev_tenant_slug)
                )
            ).scalar_one()

            original_settings = dict(tenant.settings or {})
            tenant.settings = {
                **original_settings,
                "admin_email": settings.dev_tenant_admin_email,
                "admin_password_ref": seal_secret(settings.dev_tenant_admin_password),
            }
            await session.flush()

            await ProvisioningRuntime(session)._send_welcome_email(tenant)
            await session.flush()

            persisted = (
                await session.execute(
                    text(
                        """
                        select settings
                        from tenants
                        where id=cast(:tenant_id as uuid)
                        """
                    ),
                    {"tenant_id": str(tenant.id)},
                )
            ).scalar_one()

            assert persisted["welcome_email_status"] == "FAILED"
            assert persisted["welcome_email_recipient"] == settings.dev_tenant_admin_email
            assert persisted["welcome_email_updated_at"]

            # Se jsonb_build_object receber parâmetro sem tipo e abortar a
            # transação, este SELECT falha com InFailedSQLTransactionError.
            assert await session.scalar(text("select 1")) == 1

            # A transação inteira, inclusive as precondições temporárias e o log
            # operacional criado pelo passo, é revertida ao fim do teste.
            await session.rollback()
    finally:
        # AsyncEngine/asyncpg não deve carregar conexões de um event loop pytest
        # para o próximo teste. O engine é recriado preguiçosamente na próxima
        # aquisição de conexão.
        await platform_engine.dispose()

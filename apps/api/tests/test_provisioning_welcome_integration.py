import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.db.models_platform import Tenant
from app.db.session import PlatformSession
from app.services.mail_service import MailDeliveryResult, mail_delivery
from app.services.provisioning_runtime import ProvisioningRuntime

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_welcome_email_step_updates_jsonb_without_aborting_transaction(monkeypatch) -> None:
    """Reproduz o caminho que travou SendWelcomeEmail em produção.

    O SMTP é simulado como indisponível para manter o teste determinístico. Mesmo
    com falha de entrega, o passo precisa persistir o diagnóstico no JSONB e a
    transação PostgreSQL deve continuar utilizável para que ActivateTenant possa
    executar em seguida.
    """

    def fake_delivery(**_kwargs) -> MailDeliveryResult:
        return MailDeliveryResult(
            delivered=False,
            error_code="SMTP_TEST_FAILURE",
            message="Falha SMTP simulada pelo teste de integração.",
        )

    monkeypatch.setattr(mail_delivery, "send_tenant_welcome", fake_delivery)

    async with PlatformSession() as session:
        tenant = (
            await session.execute(
                select(Tenant).where(Tenant.slug == settings.dev_tenant_slug)
            )
        ).scalar_one()

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
        assert persisted["welcome_email_recipient"]
        assert persisted["welcome_email_updated_at"]

        # Se o jsonb_build_object tiver parâmetro sem tipo e abortar a transação,
        # este SELECT também falha com InFailedSQLTransactionError.
        assert await session.scalar(text("select 1")) == 1

        # Não deixa o teste alterar permanentemente o tenant semeado.
        await session.rollback()

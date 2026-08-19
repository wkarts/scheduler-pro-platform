from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


def _future_business_slot() -> datetime:
    candidate = datetime.now(UTC).date() + timedelta(days=2)
    while int(candidate.strftime("%w")) == 0:  # domingo não faz parte do seed padrão
        candidate += timedelta(days=1)
    return datetime.combine(candidate, time(hour=10), tzinfo=UTC)


async def _login(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        headers={"host": "localhost"},
        json={
            "email": settings.dev_tenant_admin_email,
            "password": settings.dev_tenant_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["access_token"])


async def _dev_tenant_id() -> str:
    connection = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        value = await connection.fetchval(
            "select id::text from tenants where slug=$1",
            settings.dev_tenant_slug,
        )
        assert value
        return str(value)
    finally:
        await connection.close()


async def test_quick_agenda_does_not_require_optional_catalog_capabilities(
    client: httpx.AsyncClient,
) -> None:
    tenant_id = await _dev_tenant_id()
    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    optional = ["customers", "services", "professionals"]
    try:
        await platform.execute(
            """
            update tenant_capabilities
            set enabled=false, updated_at=now()
            where tenant_id=$1::uuid and capability_key=any($2::varchar[])
            """,
            tenant_id,
            optional,
        )
        token = await _login(client)
        response = await client.post(
            "/api/v1/appointments/quick",
            headers={"host": "localhost", "authorization": f"Bearer {token}"},
            json={
                "starts_at": _future_business_slot().isoformat(),
                "customer_name": f"Cliente rápido {uuid4().hex[:8]}",
                "customer_phone": f"55759{uuid4().int % 100000000:08d}",
                "service_name": f"Atendimento {uuid4().hex[:8]}",
                "duration_minutes": 30,
                "professional_name": f"Agenda {uuid4().hex[:8]}",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["id"]
        assert data["customer_id"]
        assert data["service_id"]
        assert data["professional_id"]
    finally:
        await platform.execute(
            """
            update tenant_capabilities
            set enabled=true, updated_at=now()
            where tenant_id=$1::uuid and capability_key=any($2::varchar[])
            """,
            tenant_id,
            optional,
        )
        await platform.close()


async def test_public_confirmation_updates_agenda_and_realtime_event(
    client: httpx.AsyncClient,
) -> None:
    token = await _login(client)
    starts_at = _future_business_slot() + timedelta(hours=1)
    create = await client.post(
        "/api/v1/appointments/quick",
        headers={"host": "localhost", "authorization": f"Bearer {token}"},
        json={
            "starts_at": starts_at.isoformat(),
            "customer_name": f"Confirmação {uuid4().hex[:8]}",
            "customer_phone": f"55758{uuid4().int % 100000000:08d}",
            "service_name": f"Serviço confirmação {uuid4().hex[:8]}",
            "duration_minutes": 30,
            "professional_name": f"Profissional confirmação {uuid4().hex[:8]}",
        },
    )
    assert create.status_code == 200, create.text
    appointment_id = str(create.json()["data"]["id"])

    link_response = await client.get(
        f"/api/v1/appointment-confirmations/{appointment_id}",
        headers={"host": "localhost", "authorization": f"Bearer {token}"},
    )
    assert link_response.status_code == 200, link_response.text
    request_data = link_response.json()["data"]["request"]
    confirmation_url = str(request_data["url"])
    confirmation_token = confirmation_url.rstrip("/").rsplit("/", 1)[-1]
    assert confirmation_token

    page = await client.get(f"/a/{confirmation_token}", headers={"host": "localhost"})
    assert page.status_code == 200
    assert "Confirmar agendamento" in page.text

    confirmed = await client.post(
        f"/a/{confirmation_token}/confirm",
        headers={"host": "localhost"},
    )
    assert confirmed.status_code == 200
    assert "Agendamento confirmado" in confirmed.text

    appointment = await client.get(
        f"/api/v1/appointments/{appointment_id}",
        headers={"host": "localhost", "authorization": f"Bearer {token}"},
    )
    assert appointment.status_code == 200, appointment.text
    assert appointment.json()["data"]["status"] == "CONFIRMED"

    tenant = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
        database=settings.dev_tenant_database,
    )
    try:
        event_type = await tenant.fetchval(
            """
            select event_type
            from tenant_realtime_events
            where appointment_id=$1::uuid
            order by sequence desc
            limit 1
            """,
            appointment_id,
        )
        assert event_type == "appointment.customer_confirmed"
    finally:
        await tenant.close()

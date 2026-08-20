from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.appointment_service import AppointmentService


class PublicBookingService:
    """Agenda pública do tenant sem duplicar as regras do motor interno.

    A disponibilidade e a criação passam pelo AppointmentService, portanto
    expediente, bloqueios, conflitos por profissional, confirmações e
    notificações continuam obedecendo às mesmas regras da agenda administrativa.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        public_base_url: str,
        timezone: str,
    ) -> None:
        self.session = session
        self.public_base_url = public_base_url.rstrip("/")
        self.timezone = timezone
        self.appointments = AppointmentService(
            session,
            public_base_url=self.public_base_url,
            timezone=timezone,
        )

    async def _setting(self, key: str, default: Any) -> Any:
        value = await self.session.scalar(
            text("select value from tenant_settings where key=:key limit 1"),
            {"key": key},
        )
        return default if value is None else value

    async def enabled(self) -> bool:
        return bool(await self._setting("public_booking_enabled", False))

    async def config(self) -> dict[str, Any]:
        return {
            "enabled": await self.enabled(),
            "title": str(
                await self._setting("public_booking_title", "Agende seu atendimento")
            ),
            "subtitle": str(
                await self._setting(
                    "public_booking_subtitle",
                    "Escolha o serviço, o profissional e um horário disponível.",
                )
            ),
            "success_message": str(
                await self._setting(
                    "public_booking_success_message",
                    "Seu horário foi reservado. Confira seu WhatsApp ou e-mail para confirmar o agendamento.",
                )
            ),
            "custom_html": str(
                await self._setting("public_booking_custom_html", "") or ""
            ),
            "slot_minutes": max(
                5,
                min(240, int(await self._setting("public_booking_slot_minutes", 30))),
            ),
            "minimum_notice_minutes": max(
                0,
                int(await self._setting("minimum_notice_minutes", 60)),
            ),
            "max_advance_days": max(
                1,
                int(await self._setting("max_advance_days", 90)),
            ),
            "allow_any_professional": bool(
                await self._setting("public_booking_allow_any_professional", True)
            ),
            "require_phone": bool(
                await self._setting("public_booking_require_phone", True)
            ),
            "require_email": bool(
                await self._setting("public_booking_require_email", False)
            ),
            "public_url": f"{self.public_base_url}/agendar",
        }

    async def catalog(self) -> dict[str, Any]:
        if not await self.enabled():
            raise APIError(
                "PUBLIC_BOOKING_DISABLED",
                "A agenda pública não está disponível para este estabelecimento.",
                404,
            )
        services = (
            await self.session.execute(
                text(
                    """
                    select id::text, name, duration_minutes, price
                    from services
                    where lower(coalesce(active, 'false')) in ('true','1','yes','on')
                    order by name
                    """
                )
            )
        ).mappings().all()
        professionals = (
            await self.session.execute(
                text(
                    """
                    select id::text, name
                    from professionals
                    order by name
                    """
                )
            )
        ).mappings().all()
        return {
            "config": await self.config(),
            "services": [dict(row) for row in services],
            "professionals": [dict(row) for row in professionals],
        }

    async def availability(
        self,
        *,
        day: date,
        service_id: str,
        professional_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not await self.enabled():
            raise APIError("PUBLIC_BOOKING_DISABLED", "Agenda pública desativada.", 404)
        config = await self.config()
        service_exists = await self.session.scalar(
            text(
                """
                select exists(
                  select 1 from services
                  where id=cast(:id as uuid)
                    and lower(coalesce(active, 'false')) in ('true','1','yes','on')
                )
                """
            ),
            {"id": service_id},
        )
        if not service_exists:
            raise APIError("PUBLIC_BOOKING_SERVICE_INVALID", "Serviço indisponível.", 404)

        professionals: list[dict[str, Any]]
        if professional_id:
            rows = (
                await self.session.execute(
                    text(
                        "select id::text, name from professionals "
                        "where id=cast(:id as uuid)"
                    ),
                    {"id": professional_id},
                )
            ).mappings().all()
            professionals = [dict(row) for row in rows]
        else:
            rows = (
                await self.session.execute(
                    text("select id::text, name from professionals order by name")
                )
            ).mappings().all()
            professionals = [dict(row) for row in rows]

        if not professionals:
            raise APIError(
                "PUBLIC_BOOKING_PROFESSIONAL_INVALID",
                "Nenhum profissional disponível.",
                404,
            )

        now = datetime.now(UTC)
        minimum = now + timedelta(minutes=int(config["minimum_notice_minutes"]))
        maximum = now + timedelta(days=int(config["max_advance_days"]))
        result: list[dict[str, Any]] = []
        for professional in professionals:
            slots = await self.appointments.availability(
                day=day,
                professional_id=str(professional["id"]),
                service_id=service_id,
                slot_minutes=int(config["slot_minutes"]),
            )
            for slot in slots:
                if not slot.get("available"):
                    continue
                starts_at = datetime.fromisoformat(str(slot["starts_at"]))
                if starts_at < minimum or starts_at > maximum:
                    continue
                result.append(
                    {
                        **slot,
                        "professional_name": professional["name"],
                    }
                )
        result.sort(key=lambda row: (str(row["starts_at"]), str(row["professional_name"])))
        return result

    async def _customer(
        self,
        *,
        name: str,
        phone: str | None,
        email: str | None,
    ) -> str:
        customer_id = None
        if phone:
            customer_id = await self.session.scalar(
                text(
                    """
                    select id::text from customers
                    where phone=:phone
                    order by created_at desc
                    limit 1
                    """
                ),
                {"phone": phone},
            )
        if customer_id is None and email:
            customer_id = await self.session.scalar(
                text(
                    """
                    select id::text from customers
                    where lower(coalesce(email,''))=lower(:email)
                    order by created_at desc
                    limit 1
                    """
                ),
                {"email": email},
            )
        if customer_id:
            await self.session.execute(
                text(
                    """
                    update customers set
                      name=case when length(trim(:name)) >= 2 then :name else name end,
                      phone=coalesce(:phone, phone),
                      email=coalesce(:email, email)
                    where id=cast(:id as uuid)
                    """
                ),
                {"id": str(customer_id), "name": name, "phone": phone, "email": email},
            )
            return str(customer_id)
        return str(
            await self.session.scalar(
                text(
                    """
                    insert into customers(name, phone, email, notes)
                    values(:name, :phone, :email, 'Criado pela agenda pública')
                    returning id::text
                    """
                ),
                {"name": name, "phone": phone, "email": email},
            )
        )

    async def book(
        self,
        *,
        service_id: str,
        professional_id: str,
        starts_at: datetime,
        customer_name: str,
        customer_phone: str | None,
        customer_email: str | None,
    ) -> dict[str, Any]:
        if not await self.enabled():
            raise APIError("PUBLIC_BOOKING_DISABLED", "Agenda pública desativada.", 404)
        config = await self.config()
        if bool(config["require_phone"]) and not (customer_phone or "").strip():
            raise APIError(
                "PUBLIC_BOOKING_PHONE_REQUIRED",
                "Informe um telefone/WhatsApp para continuar.",
                422,
            )
        if bool(config["require_email"]) and not (customer_email or "").strip():
            raise APIError(
                "PUBLIC_BOOKING_EMAIL_REQUIRED",
                "Informe um e-mail para continuar.",
                422,
            )

        service = (
            await self.session.execute(
                text(
                    """
                    select id::text, name, duration_minutes
                    from services
                    where id=cast(:id as uuid)
                      and lower(coalesce(active, 'false')) in ('true','1','yes','on')
                    """
                ),
                {"id": service_id},
            )
        ).mappings().first()
        if service is None:
            raise APIError("PUBLIC_BOOKING_SERVICE_INVALID", "Serviço indisponível.", 404)
        professional = (
            await self.session.execute(
                text(
                    "select id::text, name from professionals where id=cast(:id as uuid)"
                ),
                {"id": professional_id},
            )
        ).mappings().first()
        if professional is None:
            raise APIError(
                "PUBLIC_BOOKING_PROFESSIONAL_INVALID",
                "Profissional indisponível.",
                404,
            )

        aware_start = AppointmentService._aware(starts_at)
        now = datetime.now(UTC)
        if aware_start < now + timedelta(minutes=int(config["minimum_notice_minutes"])):
            raise APIError(
                "PUBLIC_BOOKING_TOO_SOON",
                "Este horário não respeita a antecedência mínima configurada.",
                409,
            )
        if aware_start > now + timedelta(days=int(config["max_advance_days"])):
            raise APIError(
                "PUBLIC_BOOKING_TOO_FAR",
                "Este horário está além do período disponível para agendamento.",
                409,
            )

        customer_id = await self._customer(
            name=customer_name.strip(),
            phone=(customer_phone or "").strip() or None,
            email=(customer_email or "").strip() or None,
        )
        await self.session.commit()
        ends_at = aware_start + timedelta(minutes=int(service["duration_minutes"] or 30))
        appointment = await self.appointments.create(
            {
                "customer_id": customer_id,
                "service_id": str(service["id"]),
                "professional_id": str(professional["id"]),
                "starts_at": aware_start,
                "ends_at": ends_at,
                "source": "public-booking",
            }
        )
        return {
            "id": str(appointment.id),
            "status": appointment.status,
            "starts_at": aware_start.isoformat(),
            "ends_at": ends_at.isoformat(),
            "service_name": service["name"],
            "professional_name": professional["name"],
            "message": config["success_message"],
        }

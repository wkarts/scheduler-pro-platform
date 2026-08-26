from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.booking_parameters_service import BookingParametersService
from app.services.flexible_appointment_service import FlexibleAppointmentService
from app.services.phone_normalization import PhoneNormalizationService


class PublicBookingService:
    """Agenda pública apoiada no mesmo motor flexível do Operador da Agenda."""

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
        self.parameters = BookingParametersService(session)
        self.appointments = FlexibleAppointmentService(
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

    async def _booking_template(self) -> dict[str, Any] | None:
        content = await self._setting("booking_page_template_content", None)
        if not isinstance(content, dict):
            return None
        return {
            "key": str(await self._setting("booking_page_template_key", "") or ""),
            "version": int(await self._setting("booking_page_template_version", 0) or 0),
            "content": content,
        }

    async def config(self) -> dict[str, Any]:
        params = await self.parameters.get()
        service_mode = str(params["service_mode"])
        email_mode = str(params["email_mode"])
        phone_mode = str(params["phone_mode"])
        duration_mode = str(params["duration_mode"])
        professional_mode = str(params["professional_mode"])
        simultaneous = params["simultaneous"] if isinstance(params["simultaneous"], dict) else {}
        return {
            "enabled": await self.enabled(),
            "title": str(
                await self._setting("public_booking_title", "Agende seu atendimento")
            ),
            "subtitle": str(
                await self._setting(
                    "public_booking_subtitle",
                    "Escolha o melhor horário e confirme seus dados.",
                )
            ),
            "success_message": str(
                await self._setting(
                    "public_booking_success_message",
                    "Seu horário foi reservado. Confira as informações de confirmação.",
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
                int(params.get("minimum_notice_minutes") or 0),
            ),
            "max_advance_days": max(
                1,
                int(await self._setting("max_advance_days", 90)),
            ),
            "allow_any_professional": bool(
                await self._setting("public_booking_allow_any_professional", True)
            ),
            "require_name": True,
            "require_phone": phone_mode == "REQUIRED",
            "service_mode": service_mode,
            "email_mode": email_mode,
            "phone_mode": phone_mode,
            "duration_mode": duration_mode,
            "professional_mode": professional_mode,
            "default_duration_minutes": int(params["default_duration_minutes"]),
            "default_professional_name": str(params["default_professional_name"]),
            "simultaneous_capacity": (
                int(simultaneous.get("capacity") or 1)
                if bool(simultaneous.get("enforce_public", True))
                else None
            ),
            "unlimited_capacity": not bool(simultaneous.get("enforce_public", True)),
            "public_url": f"{self.public_base_url}/agendar",
            "booking_template": await self._booking_template(),
        }

    async def _ensure_default_professional(self, name: str) -> dict[str, Any]:
        clean_name = name.strip() or "Agenda geral"
        row = (
            await self.session.execute(
                text(
                    "select id::text, name from professionals "
                    "where lower(name)=lower(:name) limit 1"
                ),
                {"name": clean_name},
            )
        ).mappings().first()
        if row is not None:
            return dict(row)
        created = (
            await self.session.execute(
                text(
                    "insert into professionals(name) values(:name) "
                    "returning id::text, name"
                ),
                {"name": clean_name},
            )
        ).mappings().one()
        await self.session.commit()
        return dict(created)

    async def _professionals(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        mode = str(config["professional_mode"])
        if mode == "DISABLED":
            return [
                await self._ensure_default_professional(
                    str(config["default_professional_name"])
                )
            ]
        rows = (
            await self.session.execute(
                text("select id::text, name from professionals order by name")
            )
        ).mappings().all()
        professionals = [dict(row) for row in rows]
        if professionals:
            return professionals
        return [
            await self._ensure_default_professional(
                str(config["default_professional_name"])
            )
        ]

    async def catalog(self) -> dict[str, Any]:
        if not await self.enabled():
            raise APIError(
                "PUBLIC_BOOKING_DISABLED",
                "A agenda pública não está disponível para este estabelecimento.",
                404,
            )
        config = await self.config()
        services: list[dict[str, Any]] = []
        if config["service_mode"] != "DISABLED":
            rows = (
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
            services = [dict(row) for row in rows]
        return {
            "config": config,
            "services": services,
            "professionals": await self._professionals(config),
        }

    async def _validated_service(self, service_id: str | None) -> dict[str, Any] | None:
        params = await self.parameters.get()
        mode = str(params["service_mode"])
        if mode == "DISABLED":
            return None
        if not service_id:
            if mode == "REQUIRED":
                raise APIError(
                    "PUBLIC_BOOKING_SERVICE_REQUIRED",
                    "Selecione um serviço para continuar.",
                    422,
                )
            return None
        row = (
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
        if row is None:
            raise APIError("PUBLIC_BOOKING_SERVICE_INVALID", "Serviço indisponível.", 404)
        return dict(row)

    async def _validated_professional(
        self,
        professional_id: str | None,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        mode = str(config["professional_mode"])
        if mode == "DISABLED" or not professional_id:
            if mode == "REQUIRED" and not professional_id:
                raise APIError(
                    "PUBLIC_BOOKING_PROFESSIONAL_REQUIRED",
                    "Selecione um profissional para continuar.",
                    422,
                )
            return await self._ensure_default_professional(
                str(config["default_professional_name"])
            )
        row = (
            await self.session.execute(
                text(
                    "select id::text, name from professionals "
                    "where id=cast(:id as uuid)"
                ),
                {"id": professional_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError(
                "PUBLIC_BOOKING_PROFESSIONAL_INVALID",
                "Profissional indisponível.",
                404,
            )
        return dict(row)

    async def availability(
        self,
        *,
        day: date,
        service_id: str | None = None,
        professional_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not await self.enabled():
            raise APIError("PUBLIC_BOOKING_DISABLED", "Agenda pública desativada.", 404)
        config = await self.config()
        service = await self._validated_service(service_id)
        all_professionals = await self._professionals(config)
        professionals = all_professionals
        if professional_id:
            professionals = [
                item for item in all_professionals
                if str(item["id"]) == str(professional_id)
            ]
        if not professionals:
            raise APIError(
                "PUBLIC_BOOKING_PROFESSIONAL_INVALID",
                "Nenhum responsável disponível.",
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
                service_id=str(service["id"]) if service else None,
                slot_minutes=int(config["slot_minutes"]),
                source="public-booking",
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
        result.sort(
            key=lambda row: (
                str(row["starts_at"]),
                str(row["professional_name"]),
            )
        )
        return result

    async def _customer(
        self,
        *,
        name: str,
        phone: str | None,
        email: str | None,
        phone_mode: str,
    ) -> str:
        clean_name = name.strip()
        if len(clean_name) < 2:
            raise APIError(
                "PUBLIC_BOOKING_NAME_REQUIRED",
                "Informe seu nome para continuar.",
                422,
            )
        raw_phone = str(phone or "").strip()
        if not raw_phone:
            if phone_mode == "REQUIRED":
                raise APIError(
                    "PUBLIC_BOOKING_PHONE_REQUIRED",
                    "Informe seu telefone/WhatsApp para continuar.",
                    422,
                )
            return str(
                await self.session.scalar(
                    text(
                        """
                        insert into customers(name, phone, phone_normalized, email, notes)
                        values(:name, null, null, :email, 'Criado pela agenda pública')
                        returning id::text
                        """
                    ),
                    {"name": clean_name, "email": email},
                )
            )

        phones = await PhoneNormalizationService.from_session(self.session)
        canonical = phones.normalize(raw_phone, required=True)
        assert canonical is not None
        await phones.lock_customer_phone(self.session, canonical)
        customer_id = await phones.find_customer_id(self.session, canonical)
        if customer_id:
            # Agenda pública não renomeia silenciosamente um cadastro existente.
            # O operador interno possui o fluxo explícito de confirmação.
            await self.session.execute(
                text(
                    """
                    update customers set
                      phone=:phone,
                      phone_normalized=:phone,
                      email=case when :email is null then email else :email end
                    where id=cast(:id as uuid)
                    """
                ),
                {
                    "id": customer_id,
                    "phone": canonical,
                    "email": email,
                },
            )
            return str(customer_id)
        return str(
            await self.session.scalar(
                text(
                    """
                    insert into customers(name, phone, phone_normalized, email, notes)
                    values(:name, :phone, :phone, :email, 'Criado pela agenda pública')
                    returning id::text
                    """
                ),
                {
                    "name": clean_name,
                    "phone": canonical,
                    "email": email,
                },
            )
        )

    async def book(
        self,
        *,
        service_id: str | None,
        professional_id: str | None,
        starts_at: datetime,
        customer_name: str,
        customer_phone: str | None,
        customer_email: str | None,
    ) -> dict[str, Any]:
        if not await self.enabled():
            raise APIError("PUBLIC_BOOKING_DISABLED", "Agenda pública desativada.", 404)
        config = await self.config()
        email_mode = str(config["email_mode"])
        phone_mode = str(config["phone_mode"])
        email = (customer_email or "").strip() or None
        if email_mode == "REQUIRED" and not email:
            raise APIError(
                "PUBLIC_BOOKING_EMAIL_REQUIRED",
                "Informe um e-mail para continuar.",
                422,
            )
        if email_mode == "DISABLED":
            email = None

        service = await self._validated_service(service_id)
        professional = await self._validated_professional(professional_id, config)

        aware_start = FlexibleAppointmentService._aware(starts_at)
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
            name=customer_name,
            phone=customer_phone,
            email=email,
            phone_mode=phone_mode,
        )
        duration = (
            int(service["duration_minutes"])
            if service
            else int(config["default_duration_minutes"])
        )
        ends_at = aware_start + timedelta(minutes=max(5, duration))
        appointment = await self.appointments.create(
            {
                "customer_id": customer_id,
                "service_id": str(service["id"]) if service else None,
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
            "service_name": service["name"] if service else None,
            "professional_name": professional["name"],
            "message": config["success_message"],
        }

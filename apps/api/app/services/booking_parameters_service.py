from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError


class BookingParametersService:
    SERVICE_MODES = {"DISABLED", "OPTIONAL", "REQUIRED"}
    EMAIL_MODES = {"DISABLED", "OPTIONAL", "REQUIRED"}
    KEYS = (
        "booking_service_mode",
        "booking_email_mode",
        "default_appointment_duration_minutes",
        "allow_simultaneous_public_booking",
        "allow_simultaneous_internal_booking",
        "simultaneous_booking_capacity",
        "minimum_notice_minutes",
        "phone_default_country",
        "phone_country_code",
        "phone_default_area_code",
        "phone_add_ninth_digit",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _digits(value: object) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    async def get(self) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                text(
                    "select key, value from tenant_settings "
                    "where key = any(:keys)"
                ),
                {"keys": list(self.KEYS)},
            )
        ).mappings().all()
        values = {str(row["key"]): row["value"] for row in rows}
        return {
            "service_mode": str(values.get("booking_service_mode") or "REQUIRED").upper(),
            "email_mode": str(values.get("booking_email_mode") or "OPTIONAL").upper(),
            "default_duration_minutes": int(
                values.get("default_appointment_duration_minutes") or 60
            ),
            "simultaneous": {
                "public": bool(values.get("allow_simultaneous_public_booking", False)),
                "internal": bool(values.get("allow_simultaneous_internal_booking", False)),
                "capacity": int(values.get("simultaneous_booking_capacity") or 1),
            },
            "minimum_notice_minutes": int(values.get("minimum_notice_minutes") or 1440),
            "phone": {
                "country": str(values.get("phone_default_country") or "BR").upper(),
                "country_code": str(values.get("phone_country_code") or "55"),
                "area_code": str(values.get("phone_default_area_code") or ""),
                "add_ninth_digit": bool(values.get("phone_add_ninth_digit", True)),
            },
        }

    async def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = await self.get()
        service_mode = str(payload.get("service_mode", current["service_mode"])).upper()
        email_mode = str(payload.get("email_mode", current["email_mode"])).upper()
        if service_mode not in self.SERVICE_MODES:
            raise APIError("BOOKING_SERVICE_MODE_INVALID", "Configuração de serviço inválida.", 422)
        if email_mode not in self.EMAIL_MODES:
            raise APIError("BOOKING_EMAIL_MODE_INVALID", "Configuração de e-mail inválida.", 422)

        duration = int(payload.get("default_duration_minutes", current["default_duration_minutes"]))
        if duration < 5 or duration > 720:
            raise APIError("BOOKING_DURATION_INVALID", "A duração deve ficar entre 5 e 720 minutos.", 422)

        simultaneous = payload.get("simultaneous") or current["simultaneous"]
        if not isinstance(simultaneous, dict):
            raise APIError("BOOKING_CAPACITY_INVALID", "Configuração de capacidade inválida.", 422)
        capacity = int(simultaneous.get("capacity", current["simultaneous"]["capacity"]))
        if capacity < 1 or capacity > 100:
            raise APIError("BOOKING_CAPACITY_INVALID", "A capacidade deve ficar entre 1 e 100.", 422)
        allow_public = bool(simultaneous.get("public", current["simultaneous"]["public"]))
        allow_internal = bool(simultaneous.get("internal", current["simultaneous"]["internal"]))

        minimum_notice = int(payload.get("minimum_notice_minutes", current["minimum_notice_minutes"]))
        if minimum_notice < 0 or minimum_notice > 525600:
            raise APIError("BOOKING_NOTICE_INVALID", "Antecedência mínima inválida.", 422)

        phone = payload.get("phone") or current["phone"]
        if not isinstance(phone, dict):
            raise APIError("PHONE_POLICY_INVALID", "Parâmetros de telefone inválidos.", 422)
        country = str(phone.get("country", current["phone"]["country"])).strip().upper()
        if len(country) < 2 or len(country) > 3 or not country.isalpha():
            raise APIError("PHONE_COUNTRY_INVALID", "País padrão inválido.", 422)
        country_code = self._digits(phone.get("country_code", current["phone"]["country_code"]))
        if len(country_code) < 1 or len(country_code) > 4:
            raise APIError("PHONE_COUNTRY_CODE_INVALID", "Código internacional inválido.", 422)
        area_code = self._digits(phone.get("area_code", current["phone"]["area_code"]))
        if country == "BR" and area_code and len(area_code) != 2:
            raise APIError("PHONE_AREA_CODE_INVALID", "DDD brasileiro deve possuir 2 dígitos.", 422)
        if len(area_code) > 6:
            raise APIError("PHONE_AREA_CODE_INVALID", "Código de área inválido.", 422)
        add_ninth = bool(phone.get("add_ninth_digit", current["phone"]["add_ninth_digit"]))

        values = {
            "booking_service_mode": service_mode,
            "booking_email_mode": email_mode,
            "default_appointment_duration_minutes": duration,
            "allow_simultaneous_public_booking": allow_public,
            "allow_simultaneous_internal_booking": allow_internal,
            "simultaneous_booking_capacity": capacity,
            "minimum_notice_minutes": minimum_notice,
            "phone_default_country": country,
            "phone_country_code": country_code,
            "phone_default_area_code": area_code,
            "phone_add_ninth_digit": add_ninth,
        }
        for key, value in values.items():
            await self.session.execute(
                text(
                    """
                    insert into tenant_settings(key, value, updated_at)
                    values(:key, cast(:value as jsonb), now())
                    on conflict(key) do update
                    set value=excluded.value, updated_at=now()
                    """
                ),
                {
                    "key": key,
                    "value": json.dumps(value, ensure_ascii=False),
                },
            )
        await self.session.commit()
        return await self.get()

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError


class BookingParametersService:
    FIELD_MODES = {"DISABLED", "OPTIONAL", "REQUIRED"}
    CUSTOMER_MODES = {"NEW", "EXISTING"}
    CHECKIN_FLOW_MODES = {"FULL", "SIMPLE"}
    KEYS = (
        "booking_service_mode",
        "booking_email_mode",
        "booking_phone_mode",
        "booking_duration_mode",
        "booking_professional_mode",
        "default_appointment_duration_minutes",
        "default_booking_professional_name",
        "default_booking_customer_mode",
        "allow_simultaneous_public_booking",
        "allow_simultaneous_internal_booking",
        "simultaneous_booking_capacity",
        "enforce_public_booking_capacity",
        "enforce_internal_booking_capacity",
        "enforce_business_hours",
        "enforce_blocked_periods",
        "minimum_notice_minutes",
        "phone_default_country",
        "phone_country_code",
        "phone_default_area_code",
        "phone_add_ninth_digit",
        "checkin_flow_mode",
        "checkin_notification_delay_seconds",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _digits(value: object) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    @staticmethod
    def _bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}

    @classmethod
    def _mode(cls, value: Any, default: str) -> str:
        mode = str(value or default).upper()
        return mode if mode in cls.FIELD_MODES else default

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
        customer_mode = str(values.get("default_booking_customer_mode") or "NEW").upper()
        if customer_mode not in self.CUSTOMER_MODES:
            customer_mode = "NEW"
        checkin_flow_mode = str(values.get("checkin_flow_mode") or "FULL").upper()
        if checkin_flow_mode not in self.CHECKIN_FLOW_MODES:
            checkin_flow_mode = "FULL"
        notification_delay = int(values.get("checkin_notification_delay_seconds") or 120)
        notification_delay = max(0, min(600, notification_delay))
        return {
            "service_mode": self._mode(values.get("booking_service_mode"), "REQUIRED"),
            "email_mode": self._mode(values.get("booking_email_mode"), "OPTIONAL"),
            "phone_mode": self._mode(values.get("booking_phone_mode"), "REQUIRED"),
            "duration_mode": self._mode(values.get("booking_duration_mode"), "REQUIRED"),
            "professional_mode": self._mode(values.get("booking_professional_mode"), "REQUIRED"),
            "default_duration_minutes": int(
                values.get("default_appointment_duration_minutes") or 60
            ),
            "default_professional_name": str(
                values.get("default_booking_professional_name") or "Agenda geral"
            ),
            "default_customer_mode": customer_mode,
            "checkin_flow_mode": checkin_flow_mode,
            "checkin_notification_delay_seconds": notification_delay,
            "simultaneous": {
                "public": self._bool(values.get("allow_simultaneous_public_booking"), False),
                "internal": self._bool(values.get("allow_simultaneous_internal_booking"), False),
                "capacity": int(values.get("simultaneous_booking_capacity") or 1),
                "enforce_public": self._bool(values.get("enforce_public_booking_capacity"), True),
                "enforce_internal": self._bool(values.get("enforce_internal_booking_capacity"), True),
            },
            "rules": {
                "enforce_business_hours": self._bool(values.get("enforce_business_hours"), True),
                "enforce_blocked_periods": self._bool(values.get("enforce_blocked_periods"), True),
            },
            "minimum_notice_minutes": int(values.get("minimum_notice_minutes") or 1440),
            "phone": {
                "country": str(values.get("phone_default_country") or "BR").upper(),
                "country_code": str(values.get("phone_country_code") or "55"),
                "area_code": str(values.get("phone_default_area_code") or ""),
                "add_ninth_digit": self._bool(values.get("phone_add_ninth_digit"), True),
            },
        }

    async def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = await self.get()
        modes: dict[str, str] = {}
        for key, default in (
            ("service_mode", current["service_mode"]),
            ("email_mode", current["email_mode"]),
            ("phone_mode", current["phone_mode"]),
            ("duration_mode", current["duration_mode"]),
            ("professional_mode", current["professional_mode"]),
        ):
            mode = str(payload.get(key, default)).upper()
            if mode not in self.FIELD_MODES:
                raise APIError(
                    "BOOKING_FIELD_MODE_INVALID",
                    f"Configuração inválida para {key}.",
                    422,
                )
            modes[key] = mode

        duration = int(payload.get("default_duration_minutes", current["default_duration_minutes"]))
        if duration < 5 or duration > 720:
            raise APIError(
                "BOOKING_DURATION_INVALID",
                "A duração deve ficar entre 5 e 720 minutos.",
                422,
            )

        default_professional_name = str(
            payload.get("default_professional_name", current["default_professional_name"])
        ).strip()
        if len(default_professional_name) < 2 or len(default_professional_name) > 160:
            raise APIError(
                "BOOKING_DEFAULT_PROFESSIONAL_INVALID",
                "O nome padrão do responsável deve possuir entre 2 e 160 caracteres.",
                422,
            )
        default_customer_mode = str(
            payload.get("default_customer_mode", current["default_customer_mode"])
        ).upper()
        if default_customer_mode not in self.CUSTOMER_MODES:
            raise APIError(
                "BOOKING_DEFAULT_CUSTOMER_MODE_INVALID",
                "A abertura padrão deve ser Novo cliente ou Cliente existente.",
                422,
            )

        checkin_flow_mode = str(
            payload.get("checkin_flow_mode", current["checkin_flow_mode"])
        ).upper()
        if checkin_flow_mode not in self.CHECKIN_FLOW_MODES:
            raise APIError(
                "CHECKIN_FLOW_MODE_INVALID",
                "O fluxo de Check-in deve ser Completo ou Simplificado.",
                422,
            )
        notification_delay = int(
            payload.get(
                "checkin_notification_delay_seconds",
                current["checkin_notification_delay_seconds"],
            )
        )
        if notification_delay < 0 or notification_delay > 600:
            raise APIError(
                "CHECKIN_NOTIFICATION_DELAY_INVALID",
                "A espera das notificações deve ficar entre 0 e 600 segundos.",
                422,
            )

        simultaneous = payload.get("simultaneous") or current["simultaneous"]
        if not isinstance(simultaneous, dict):
            raise APIError(
                "BOOKING_CAPACITY_INVALID",
                "Configuração de capacidade inválida.",
                422,
            )
        capacity = int(simultaneous.get("capacity", current["simultaneous"]["capacity"]))
        if capacity < 1 or capacity > 10000:
            raise APIError(
                "BOOKING_CAPACITY_INVALID",
                "A capacidade deve ficar entre 1 e 10000.",
                422,
            )
        allow_public = bool(simultaneous.get("public", current["simultaneous"]["public"]))
        allow_internal = bool(
            simultaneous.get("internal", current["simultaneous"]["internal"])
        )
        enforce_public = bool(
            simultaneous.get("enforce_public", current["simultaneous"]["enforce_public"])
        )
        enforce_internal = bool(
            simultaneous.get(
                "enforce_internal",
                current["simultaneous"]["enforce_internal"],
            )
        )

        rules = payload.get("rules") or current["rules"]
        if not isinstance(rules, dict):
            raise APIError("BOOKING_RULES_INVALID", "Regras de agenda inválidas.", 422)
        enforce_business_hours = bool(
            rules.get("enforce_business_hours", current["rules"]["enforce_business_hours"])
        )
        enforce_blocked_periods = bool(
            rules.get("enforce_blocked_periods", current["rules"]["enforce_blocked_periods"])
        )

        minimum_notice = int(
            payload.get("minimum_notice_minutes", current["minimum_notice_minutes"])
        )
        if minimum_notice < 0 or minimum_notice > 525600:
            raise APIError(
                "BOOKING_NOTICE_INVALID",
                "Antecedência mínima inválida.",
                422,
            )

        phone = payload.get("phone") or current["phone"]
        if not isinstance(phone, dict):
            raise APIError("PHONE_POLICY_INVALID", "Parâmetros de telefone inválidos.", 422)
        country = str(phone.get("country", current["phone"]["country"])).strip().upper()
        if len(country) < 2 or len(country) > 3 or not country.isalpha():
            raise APIError("PHONE_COUNTRY_INVALID", "País padrão inválido.", 422)
        country_code = self._digits(
            phone.get("country_code", current["phone"]["country_code"])
        )
        if len(country_code) < 1 or len(country_code) > 4:
            raise APIError(
                "PHONE_COUNTRY_CODE_INVALID",
                "Código internacional inválido.",
                422,
            )
        area_code = self._digits(phone.get("area_code", current["phone"]["area_code"]))
        if country == "BR" and area_code and len(area_code) != 2:
            raise APIError(
                "PHONE_AREA_CODE_INVALID",
                "DDD brasileiro deve possuir 2 dígitos.",
                422,
            )
        if len(area_code) > 6:
            raise APIError("PHONE_AREA_CODE_INVALID", "Código de área inválido.", 422)
        add_ninth = bool(
            phone.get("add_ninth_digit", current["phone"]["add_ninth_digit"])
        )

        values = {
            "booking_service_mode": modes["service_mode"],
            "booking_email_mode": modes["email_mode"],
            "booking_phone_mode": modes["phone_mode"],
            "booking_duration_mode": modes["duration_mode"],
            "booking_professional_mode": modes["professional_mode"],
            "default_appointment_duration_minutes": duration,
            "default_booking_professional_name": default_professional_name,
            "default_booking_customer_mode": default_customer_mode,
            "checkin_flow_mode": checkin_flow_mode,
            "checkin_notification_delay_seconds": notification_delay,
            "allow_simultaneous_public_booking": allow_public,
            "allow_simultaneous_internal_booking": allow_internal,
            "simultaneous_booking_capacity": capacity,
            "enforce_public_booking_capacity": enforce_public,
            "enforce_internal_booking_capacity": enforce_internal,
            "enforce_business_hours": enforce_business_hours,
            "enforce_blocked_periods": enforce_blocked_periods,
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

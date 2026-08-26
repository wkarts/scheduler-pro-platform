from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError

_DIGITS = re.compile(r"\D+")


@dataclass(frozen=True, slots=True)
class PhonePolicy:
    country: str = "BR"
    country_code: str = "55"
    area_code: str = ""
    add_ninth_digit: bool = True

    @classmethod
    async def load(cls, session: AsyncSession) -> "PhonePolicy":
        rows = (
            await session.execute(
                text(
                    """
                    select key, value
                    from tenant_settings
                    where key in (
                      'phone_default_country',
                      'phone_country_code',
                      'phone_default_area_code',
                      'phone_add_ninth_digit'
                    )
                    """
                )
            )
        ).mappings().all()
        values: dict[str, Any] = {str(row["key"]): row["value"] for row in rows}
        return cls(
            country=str(values.get("phone_default_country") or "BR").upper().strip(),
            country_code=_digits_only(values.get("phone_country_code") or "55"),
            area_code=_digits_only(values.get("phone_default_area_code") or ""),
            add_ninth_digit=_as_bool(values.get("phone_add_ninth_digit"), True),
        )


def _digits_only(value: object) -> str:
    return _DIGITS.sub("", str(value or ""))


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


class PhoneNormalizationService:
    """Único ponto de normalização operacional de telefones do Scheduler Pro.

    O valor canônico contém somente dígitos. A regra brasileira reconhece código
    do país, DDD e nono dígito antes de acrescentar qualquer parte, mantendo a
    operação idempotente. Para outros países, a política não tenta inventar uma
    estrutura nacional desconhecida: acrescenta somente prefixos explicitamente
    configurados quando ausentes.
    """

    def __init__(self, policy: PhonePolicy) -> None:
        self.policy = policy

    @classmethod
    async def from_session(cls, session: AsyncSession) -> "PhoneNormalizationService":
        return cls(await PhonePolicy.load(session))

    def normalize(self, value: str | None, *, required: bool = False) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            if required:
                raise APIError("PHONE_REQUIRED", "Informe o telefone/WhatsApp.", 422)
            return None

        digits = _digits_only(raw)
        if digits.startswith("00"):
            digits = digits[2:]
        if not digits:
            if required:
                raise APIError("PHONE_INVALID", "Telefone/WhatsApp inválido.", 422)
            return None

        if self.policy.country == "BR" or self.policy.country_code == "55":
            return self._normalize_br(digits)
        return self._normalize_generic(digits)

    def _normalize_br(self, digits: str) -> str:
        country_code = self.policy.country_code or "55"
        has_country = digits.startswith(country_code) and len(digits) > len(country_code) + 9
        national = digits[len(country_code):] if has_country else digits

        if len(national) in {8, 9}:
            if not self.policy.area_code:
                raise APIError(
                    "PHONE_AREA_CODE_REQUIRED",
                    "Configure o DDD padrão ou informe o telefone com DDD.",
                    422,
                )
            national = f"{self.policy.area_code}{national}"
        elif len(national) not in {10, 11}:
            raise APIError("PHONE_INVALID", "Telefone/WhatsApp brasileiro inválido.", 422)

        area_code = national[:2]
        local = national[2:]
        if len(area_code) != 2 or area_code.startswith("0"):
            raise APIError("PHONE_INVALID_AREA_CODE", "DDD do telefone inválido.", 422)

        if self.policy.add_ninth_digit and len(local) == 8:
            local = f"9{local}"
        if len(local) not in {8, 9}:
            raise APIError("PHONE_INVALID", "Telefone/WhatsApp brasileiro inválido.", 422)

        canonical = f"{country_code}{area_code}{local}"
        # A saída deste método já contém país + DDD; uma nova chamada reconhecerá
        # o país e produzirá exatamente o mesmo resultado.
        return canonical

    def _normalize_generic(self, digits: str) -> str:
        country_code = self.policy.country_code
        if not country_code:
            raise APIError(
                "PHONE_COUNTRY_CODE_REQUIRED",
                "Configure o código internacional padrão.",
                422,
            )
        if digits.startswith(country_code):
            return digits
        if self.policy.area_code and not digits.startswith(self.policy.area_code):
            digits = f"{self.policy.area_code}{digits}"
        return f"{country_code}{digits}"

    def equivalent_digits(self, canonical: str) -> set[str]:
        """Formas numéricas úteis para localizar registros legados sem full scan."""
        canonical = _digits_only(canonical)
        candidates = {canonical}
        country_code = self.policy.country_code
        national = canonical
        if country_code and canonical.startswith(country_code):
            national = canonical[len(country_code):]
            candidates.add(national)
        if self.policy.country == "BR" and len(national) in {10, 11}:
            local = national[2:]
            candidates.add(local)
            if len(local) == 9 and local.startswith("9"):
                candidates.add(local[1:])
                candidates.add(f"{national[:2]}{local[1:]}")
        return {item for item in candidates if item}

    async def find_customer_id(self, session: AsyncSession, canonical: str) -> str | None:
        values = sorted(self.equivalent_digits(canonical), key=len, reverse=True)
        row = (
            await session.execute(
                text(
                    """
                    select id::text, phone, phone_normalized
                    from customers
                    where phone_normalized=:canonical
                       or regexp_replace(coalesce(phone,''), '[^0-9]', '', 'g') = any(:variants)
                    order by case when phone_normalized=:canonical then 0 else 1 end,
                             created_at desc
                    limit 20
                    """
                ),
                {"canonical": canonical, "variants": values},
            )
        ).mappings().all()
        for candidate in row:
            existing_normalized = str(candidate.get("phone_normalized") or "")
            if existing_normalized == canonical:
                return str(candidate["id"])
            try:
                if self.normalize(str(candidate.get("phone") or "")) == canonical:
                    return str(candidate["id"])
            except APIError:
                continue
        return None

    async def lock_customer_phone(self, session: AsyncSession, canonical: str) -> None:
        await session.execute(
            text("select pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"scheduler-pro:customer-phone:{canonical}"},
        )

    async def normalize_customer_phone(
        self,
        session: AsyncSession,
        *,
        customer_id: str,
        value: str,
    ) -> str:
        canonical = self.normalize(value, required=True)
        assert canonical is not None
        await self.lock_customer_phone(session, canonical)
        conflict_id = await self.find_customer_id(session, canonical)
        if conflict_id is not None and conflict_id != customer_id:
            raise APIError(
                "CUSTOMER_PHONE_CONFLICT",
                "Já existe um cliente desta empresa com este telefone/WhatsApp.",
                409,
                {"conflict_customer_id": conflict_id},
            )
        await session.execute(
            text(
                """
                update customers
                set phone=:canonical, phone_normalized=:canonical
                where id=cast(:id as uuid)
                """
            ),
            {"id": customer_id, "canonical": canonical},
        )
        return canonical

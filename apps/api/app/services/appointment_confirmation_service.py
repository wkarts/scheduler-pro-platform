from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.secrets import seal_secret, secret_resolver
from app.services.link_shortener import link_shortener


class AppointmentConfirmationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def _setting(self, key: str, default: Any) -> Any:
        value = await self.session.scalar(
            text("select value from tenant_settings where key=:key limit 1"),
            {"key": key},
        )
        return default if value is None else value

    async def confirmation_required(self) -> bool:
        value = await self._setting("confirmation_required", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
                "não",
                "nao",
            }
        return bool(value)

    async def _deadline_minutes(self) -> int:
        value = await self._setting("confirmation_deadline_minutes", 60)
        try:
            return min(max(int(value), 0), 7 * 24 * 60)
        except (TypeError, ValueError):
            return 60

    async def _link_ttl_hours(self) -> int:
        value = await self._setting("confirmation_link_ttl_hours", 168)
        try:
            return min(max(int(value), 1), 24 * 30)
        except (TypeError, ValueError):
            return 168

    async def _shortener_settings(self) -> tuple[bool, str, dict[str, Any]]:
        enabled = await self._setting("short_links_enabled", False)
        provider = str(await self._setting("short_links_provider", "none") or "none")
        config = await self._setting("short_links_config", {})
        return bool(enabled), provider, config if isinstance(config, dict) else {}

    async def public_base_url(self, fallback: str | None = None) -> str:
        configured = str(await self._setting("public_base_url", "") or "").strip()
        value = configured or str(fallback or "").strip()
        if not value:
            raise APIError(
                "CONFIRMATION_PUBLIC_URL_MISSING",
                "URL pública do tenant não está configurada.",
                500,
            )
        return value.rstrip("/")

    async def ensure_request(
        self,
        appointment_id: str,
        *,
        public_base_url: str | None = None,
        rotate: bool = False,
    ) -> dict[str, Any] | None:
        if not await self.confirmation_required():
            return None

        appointment = (
            await self.session.execute(
                text(
                    """
                    select id::text, starts_at, ends_at, status
                    from appointments
                    where id=cast(:appointment_id as uuid)
                    """
                ),
                {"appointment_id": appointment_id},
            )
        ).mappings().first()
        if appointment is None:
            raise APIError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.", 404)

        starts_at = appointment["starts_at"]
        if not isinstance(starts_at, datetime):
            raise APIError(
                "APPOINTMENT_START_INVALID",
                "Horário do agendamento inválido.",
                500,
            )
        now = datetime.now(UTC)
        if starts_at <= now:
            raise APIError(
                "CONFIRMATION_APPOINTMENT_ALREADY_STARTED",
                "O atendimento já iniciou e não pode receber novo link de confirmação.",
                409,
            )

        deadline_minutes = await self._deadline_minutes()
        requested_deadline = starts_at - timedelta(minutes=deadline_minutes)
        confirmation_deadline = min(
            starts_at,
            max(requested_deadline, now + timedelta(minutes=5)),
        )
        ttl_hours = await self._link_ttl_hours()
        expires_at = min(
            starts_at + timedelta(hours=2),
            now + timedelta(hours=ttl_hours),
        )

        current = (
            await self.session.execute(
                text(
                    """
                    select id::text, token_ref, state, confirmation_deadline,
                           expires_at, response, responded_at
                    from appointment_confirmation_requests
                    where appointment_id=cast(:appointment_id as uuid)
                    """
                ),
                {"appointment_id": appointment_id},
            )
        ).mappings().first()

        can_reuse = False
        if current is not None:
            current_expires_at = current["expires_at"]
            can_reuse = (
                not rotate
                and str(current["state"]) == "PENDING"
                and isinstance(current_expires_at, datetime)
                and current_expires_at > now
            )

        if can_reuse and current is not None:
            token = secret_resolver.resolve(str(current["token_ref"]))
            request_id = str(current["id"])
        else:
            token = secrets.token_urlsafe(18)
            token_hash = self._token_hash(token)
            token_ref = seal_secret(token)
            row = (
                await self.session.execute(
                    text(
                        """
                        insert into appointment_confirmation_requests(
                          appointment_id, token_hash, token_ref, state,
                          confirmation_deadline, expires_at, response,
                          responded_at, updated_at
                        ) values(
                          cast(:appointment_id as uuid), :token_hash, :token_ref,
                          'PENDING', :confirmation_deadline, :expires_at, null, null, now()
                        )
                        on conflict(appointment_id) do update set
                          token_hash=excluded.token_hash,
                          token_ref=excluded.token_ref,
                          state='PENDING',
                          confirmation_deadline=excluded.confirmation_deadline,
                          expires_at=excluded.expires_at,
                          response=null,
                          responded_at=null,
                          updated_at=now()
                        returning id::text
                        """
                    ),
                    {
                        "appointment_id": appointment_id,
                        "token_hash": token_hash,
                        "token_ref": token_ref,
                        "confirmation_deadline": confirmation_deadline,
                        "expires_at": expires_at,
                    },
                )
            ).mappings().one()
            request_id = str(row["id"])

        base_url = await self.public_base_url(public_base_url)
        canonical_url = f"{base_url}/a/{token}"
        short_enabled, short_provider, short_config = await self._shortener_settings()
        shortened = await link_shortener.shorten(
            canonical_url,
            enabled=short_enabled,
            provider=short_provider,
            config=short_config,
        )
        return {
            "id": request_id,
            "appointment_id": appointment_id,
            "url": shortened.url,
            "canonical_url": canonical_url,
            "shortened": shortened.shortened,
            "shortener_provider": shortened.provider,
            "confirmation_deadline": confirmation_deadline,
            "expires_at": expires_at,
        }

    async def snapshot(self, token: str) -> dict[str, Any]:
        token_hash = self._token_hash(token)
        row = (
            await self.session.execute(
                text(
                    """
                    select acr.id::text as request_id, acr.appointment_id::text,
                           acr.state, acr.confirmation_deadline, acr.expires_at,
                           acr.response, acr.responded_at,
                           a.starts_at, a.ends_at, a.status,
                           c.name as customer_name, c.phone as customer_phone,
                           s.name as service_name, s.duration_minutes,
                           p.name as professional_name
                    from appointment_confirmation_requests acr
                    join appointments a on a.id=acr.appointment_id
                    join customers c on c.id=a.customer_id
                    join services s on s.id=a.service_id
                    join professionals p on p.id=a.professional_id
                    where acr.token_hash=:token_hash
                    limit 1
                    """
                ),
                {"token_hash": token_hash},
            )
        ).mappings().first()
        if row is None:
            raise APIError(
                "CONFIRMATION_LINK_INVALID",
                "Link de confirmação inválido ou substituído.",
                404,
            )
        data = dict(row)
        now = datetime.now(UTC)
        expires_at = data.get("expires_at")
        deadline = data.get("confirmation_deadline")
        data["link_expired"] = (
            isinstance(expires_at, datetime) and expires_at <= now
        )
        data["deadline_expired"] = (
            isinstance(deadline, datetime) and deadline <= now
        )
        data["can_respond"] = (
            data["state"] == "PENDING"
            and not data["link_expired"]
            and not data["deadline_expired"]
            and data["status"]
            not in {"COMPLETED", "CANCELLED", "NO_SHOW", "CONFIRMED"}
        )
        return data

    async def _apply_appointment_response(
        self,
        appointment_id: str,
        *,
        status: str,
        reason: str,
    ) -> None:
        from app.services.notification_service import NotificationService

        current = await self.session.scalar(
            text("select status from appointments where id=cast(:id as uuid)"),
            {"id": appointment_id},
        )
        if current is None:
            raise APIError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.", 404)
        if str(current) in {"COMPLETED", "CANCELLED", "NO_SHOW"}:
            raise APIError(
                "APPOINTMENT_FINAL_STATUS",
                "Este agendamento já foi finalizado.",
                409,
            )
        await self.session.execute(
            text(
                "update appointments set status=:status "
                "where id=cast(:id as uuid)"
            ),
            {"id": appointment_id, "status": status},
        )
        await self.session.execute(
            text(
                """
                insert into appointment_status_history(appointment_id, status, reason)
                values(cast(:id as uuid), :status, :reason)
                """
            ),
            {"id": appointment_id, "status": status, "reason": reason},
        )
        await NotificationService(self.session).schedule_for_appointment(
            appointment_id,
            f"appointment_{status.lower()}",
            reason=reason,
        )

    async def respond(self, token: str, action: str) -> dict[str, Any]:
        normalized = action.strip().upper()
        if normalized not in {"CONFIRM", "CANCEL"}:
            raise APIError("CONFIRMATION_ACTION_INVALID", "Ação inválida.", 422)

        data = await self.snapshot(token)
        if not data["can_respond"]:
            if data["state"] in {"CONFIRMED", "CANCELLED"}:
                return data
            raise APIError(
                "CONFIRMATION_WINDOW_EXPIRED",
                "O prazo para responder a este agendamento expirou.",
                409,
                {"state": data["state"], "appointment_status": data["status"]},
            )

        await self.session.execute(
            text("select pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"appointment-confirmation:{data['appointment_id']}"},
        )
        refreshed = await self.snapshot(token)
        if not refreshed["can_respond"]:
            return refreshed

        if normalized == "CONFIRM":
            request_state = "CONFIRMED"
            template_key = "tenant_confirmation_confirmed"
            appointment_status = "CONFIRMED"
            reason = "Confirmado pelo cliente através do link público"
        else:
            request_state = "CANCELLED"
            template_key = "tenant_confirmation_cancelled"
            appointment_status = "CANCELLED"
            reason = "Cancelado pelo cliente através do link público"

        claimed = await self.session.scalar(
            text(
                """
                update appointment_confirmation_requests
                set state=:state, response=:state, responded_at=now(), updated_at=now()
                where id=cast(:id as uuid) and state='PENDING'
                  and confirmation_deadline > now() and expires_at > now()
                returning id::text
                """
            ),
            {"id": refreshed["request_id"], "state": request_state},
        )
        if not claimed:
            await self.session.rollback()
            return await self.snapshot(token)

        await self._apply_appointment_response(
            str(refreshed["appointment_id"]),
            status=appointment_status,
            reason=reason,
        )
        from app.services.notification_service import NotificationService

        await NotificationService(self.session).notify_tenant_confirmation_result(
            str(refreshed["appointment_id"]),
            template_key,
        )
        await self.session.commit()
        return await self.snapshot(token)

    async def expire_due(self, *, limit: int = 200) -> dict[str, int]:
        rows = (
            await self.session.execute(
                text(
                    """
                    select acr.id::text as request_id, acr.appointment_id::text
                    from appointment_confirmation_requests acr
                    join appointments a on a.id=acr.appointment_id
                    where acr.state='PENDING'
                      and acr.confirmation_deadline <= now()
                      and a.status in ('PENDING','AWAITING_CONFIRMATION','RESCHEDULED')
                    order by acr.confirmation_deadline asc
                    limit :limit
                    for update of acr skip locked
                    """
                ),
                {"limit": min(max(limit, 1), 1000)},
            )
        ).mappings().all()
        if not rows:
            return {"expired": 0, "failed": 0}

        from app.services.notification_service import NotificationService

        expired = 0
        failed = 0
        for row in rows:
            try:
                appointment_id = str(row["appointment_id"])
                claimed = await self.session.scalar(
                    text(
                        """
                        update appointment_confirmation_requests
                        set state='EXPIRED', response='EXPIRED',
                            responded_at=now(), updated_at=now()
                        where id=cast(:id as uuid) and state='PENDING'
                          and confirmation_deadline <= now()
                        returning id::text
                        """
                    ),
                    {"id": row["request_id"]},
                )
                if not claimed:
                    continue
                await self._apply_appointment_response(
                    appointment_id,
                    status="CANCELLED",
                    reason=(
                        "Prazo de confirmação expirado; "
                        "horário liberado automaticamente"
                    ),
                )
                await NotificationService(
                    self.session
                ).notify_tenant_confirmation_result(
                    appointment_id,
                    "tenant_confirmation_expired",
                )
                await self.session.commit()
                expired += 1
            except Exception:  # noqa: BLE001 - um agendamento não para a varredura
                await self.session.rollback()
                failed += 1
        return {"expired": expired, "failed": failed}

    async def page_settings(self) -> dict[str, str]:
        defaults = {
            "confirmation_page_title": "Confirme seu atendimento",
            "confirmation_page_message": (
                "Revise os dados abaixo e confirme ou cancele seu horário."
            ),
            "confirmation_confirm_label": "Confirmar agendamento",
            "confirmation_cancel_label": "Cancelar agendamento",
        }
        result: dict[str, str] = {}
        for key, default in defaults.items():
            result[key] = str(await self._setting(key, default) or default)
        return result

    async def notification_preferences(self) -> dict[str, Any]:
        return {
            "tenant_notification_whatsapp": str(
                await self._setting("tenant_notification_whatsapp", "") or ""
            ).strip(),
            "confirmation_required": await self.confirmation_required(),
            "confirmation_deadline_minutes": await self._deadline_minutes(),
            "short_links_enabled": bool(
                await self._setting("short_links_enabled", False)
            ),
            "short_links_provider": str(
                await self._setting("short_links_provider", "none") or "none"
            ),
        }

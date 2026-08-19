from __future__ import annotations

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.secrets import seal_secret, secret_resolver


@dataclass(frozen=True)
class TenantSmtpConfig:
    enabled: bool
    host: str
    port: int
    username: str
    password_ref: str
    from_email: str
    from_name: str
    reply_to: str
    use_tls: bool
    use_ssl: bool
    timeout_seconds: int

    @property
    def configured(self) -> bool:
        auth_ready = not self.username or bool(self.password_ref)
        return bool(self.host and self.from_email and auth_ready)


class TenantMailService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _row(self) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    select enabled, host, port, username, password_ref,
                           from_email, from_name, reply_to, use_tls, use_ssl,
                           timeout_seconds, updated_at
                    from tenant_smtp_settings
                    where singleton=1
                    """
                )
            )
        ).mappings().first()
        return dict(row) if row else None

    async def status(self) -> dict[str, Any]:
        row = await self._row()
        if row is None:
            return {
                "enabled": False,
                "configured": False,
                "host": "",
                "port": 587,
                "username": "",
                "from_email": "",
                "from_name": "",
                "reply_to": "",
                "use_tls": True,
                "use_ssl": False,
                "timeout_seconds": 15,
                "password_configured": False,
                "updated_at": None,
            }
        username = str(row["username"] or "")
        password_configured = bool(row["password_ref"])
        return {
            "enabled": bool(row["enabled"]),
            "configured": bool(
                row["host"]
                and row["from_email"]
                and (not username or password_configured)
            ),
            "host": str(row["host"] or ""),
            "port": int(row["port"] or 587),
            "username": username,
            "from_email": str(row["from_email"] or ""),
            "from_name": str(row["from_name"] or ""),
            "reply_to": str(row["reply_to"] or ""),
            "use_tls": bool(row["use_tls"]),
            "use_ssl": bool(row["use_ssl"]),
            "timeout_seconds": int(row["timeout_seconds"] or 15),
            "password_configured": password_configured,
            "updated_at": row["updated_at"],
        }

    async def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = await self._row() or {}
        host = str(payload.get("host", current.get("host") or "")).strip()
        username = str(payload.get("username", current.get("username") or "")).strip()
        from_email = str(payload.get("from_email", current.get("from_email") or "")).strip()
        from_name = str(payload.get("from_name", current.get("from_name") or "")).strip()
        reply_to = str(payload.get("reply_to", current.get("reply_to") or "")).strip()
        port = int(payload.get("port", current.get("port") or 587))
        timeout_seconds = int(
            payload.get("timeout_seconds", current.get("timeout_seconds") or 15)
        )
        use_tls = bool(payload.get("use_tls", current.get("use_tls", True)))
        use_ssl = bool(payload.get("use_ssl", current.get("use_ssl", False)))
        enabled = bool(payload.get("enabled", current.get("enabled", False)))
        password = str(payload.get("password") or "")
        password_ref = str(current.get("password_ref") or "")
        if password:
            password_ref = seal_secret(password)
        if not username:
            password_ref = ""
        if port < 1 or port > 65535:
            raise APIError("TENANT_SMTP_PORT_INVALID", "Porta SMTP inválida.", 422)
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise APIError("TENANT_SMTP_TIMEOUT_INVALID", "Timeout SMTP inválido.", 422)
        if use_tls and use_ssl:
            raise APIError(
                "TENANT_SMTP_SECURITY_INVALID",
                "Escolha STARTTLS ou SSL/TLS, não ambos.",
                422,
            )
        auth_ready = not username or bool(password_ref)
        if enabled and (not host or not from_email or not auth_ready):
            raise APIError(
                "TENANT_SMTP_INCOMPLETE",
                "Para ativar o e-mail informe servidor, remetente e, quando houver usuário, a senha SMTP.",
                422,
            )
        await self.session.execute(
            text(
                """
                insert into tenant_smtp_settings(
                  singleton, enabled, host, port, username, password_ref,
                  from_email, from_name, reply_to, use_tls, use_ssl,
                  timeout_seconds, updated_at
                ) values(
                  1, :enabled, :host, :port, :username, :password_ref,
                  :from_email, :from_name, :reply_to, :use_tls, :use_ssl,
                  :timeout_seconds, now()
                )
                on conflict(singleton) do update set
                  enabled=excluded.enabled,
                  host=excluded.host,
                  port=excluded.port,
                  username=excluded.username,
                  password_ref=excluded.password_ref,
                  from_email=excluded.from_email,
                  from_name=excluded.from_name,
                  reply_to=excluded.reply_to,
                  use_tls=excluded.use_tls,
                  use_ssl=excluded.use_ssl,
                  timeout_seconds=excluded.timeout_seconds,
                  updated_at=now()
                """
            ),
            {
                "enabled": enabled,
                "host": host or None,
                "port": port,
                "username": username or None,
                "password_ref": password_ref or None,
                "from_email": from_email or None,
                "from_name": from_name or None,
                "reply_to": reply_to or None,
                "use_tls": use_tls,
                "use_ssl": use_ssl,
                "timeout_seconds": timeout_seconds,
            },
        )
        await self.session.commit()
        return await self.status()

    async def config(self, *, require_enabled: bool = True) -> TenantSmtpConfig | None:
        row = await self._row()
        if not row:
            return None
        config = TenantSmtpConfig(
            enabled=bool(row["enabled"]),
            host=str(row["host"] or ""),
            port=int(row["port"] or 587),
            username=str(row["username"] or ""),
            password_ref=str(row["password_ref"] or ""),
            from_email=str(row["from_email"] or ""),
            from_name=str(row["from_name"] or ""),
            reply_to=str(row["reply_to"] or ""),
            use_tls=bool(row["use_tls"]),
            use_ssl=bool(row["use_ssl"]),
            timeout_seconds=int(row["timeout_seconds"] or 15),
        )
        if not config.configured or (require_enabled and not config.enabled):
            return None
        return config

    @staticmethod
    def _send_sync(
        config: TenantSmtpConfig,
        to: str,
        subject: str,
        body: str,
    ) -> None:
        password = (
            secret_resolver.resolve(config.password_ref)
            if config.username and config.password_ref
            else ""
        )
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = (
            f"{config.from_name} <{config.from_email}>"
            if config.from_name
            else config.from_email
        )
        message["To"] = to
        if config.reply_to:
            message["Reply-To"] = config.reply_to
        message.set_content(body)
        context = ssl.create_default_context()
        if config.use_ssl:
            with smtplib.SMTP_SSL(
                config.host,
                config.port,
                timeout=config.timeout_seconds,
                context=context,
            ) as client:
                if config.username:
                    client.login(config.username, password)
                client.send_message(message)
            return
        with smtplib.SMTP(
            config.host,
            config.port,
            timeout=config.timeout_seconds,
        ) as client:
            client.ehlo()
            if config.use_tls:
                client.starttls(context=context)
                client.ehlo()
            if config.username:
                client.login(config.username, password)
            client.send_message(message)

    async def send(self, to: str, subject: str, body: str) -> None:
        config = await self.config(require_enabled=True)
        if config is None:
            raise APIError(
                "TENANT_SMTP_DISABLED",
                "SMTP do tenant não está ativo.",
                409,
            )
        await asyncio.to_thread(self._send_sync, config, to, subject, body)

    async def send_test(self, recipient: str) -> dict[str, Any]:
        recipient = recipient.strip()
        if not recipient:
            raise APIError(
                "TENANT_SMTP_TEST_RECIPIENT_REQUIRED",
                "Informe o destinatário do teste.",
                422,
            )
        await self.send(
            recipient,
            "Scheduler Pro — teste SMTP",
            "Esta mensagem confirma que o SMTP deste tenant está configurado e enviando corretamente.",
        )
        return {"sent": True, "recipient": recipient}

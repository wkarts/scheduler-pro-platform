from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MailDeliveryResult:
    delivered: bool
    error_code: str | None = None
    message: str | None = None


class MailDeliveryService:
    """Entrega e-mails transacionais usando exclusivamente o SMTP do ambiente."""

    @property
    def enabled(self) -> bool:
        return bool(settings.smtp_host and settings.smtp_from_email)

    def status(self) -> dict[str, object]:
        return {
            "configured": self.enabled,
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "from_email": settings.smtp_from_email,
            "from_name": settings.smtp_from_name,
            "reply_to": settings.smtp_reply_to,
            "use_tls": settings.smtp_use_tls,
            "use_ssl": settings.smtp_use_ssl,
            "timeout_seconds": settings.smtp_timeout_seconds,
            "authentication_configured": bool(settings.smtp_username),
        }

    @staticmethod
    def _failure(exc: BaseException) -> MailDeliveryResult:
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            return MailDeliveryResult(False, "SMTP_AUTH", "Autenticação SMTP rejeitada pelo servidor.")
        if isinstance(exc, smtplib.SMTPRecipientsRefused):
            return MailDeliveryResult(False, "SMTP_RECIPIENT", "O servidor SMTP rejeitou o destinatário.")
        if isinstance(exc, smtplib.SMTPSenderRefused):
            return MailDeliveryResult(False, "SMTP_SENDER", "O servidor SMTP rejeitou o remetente configurado.")
        if isinstance(exc, TimeoutError):
            return MailDeliveryResult(False, "SMTP_TIMEOUT", "Tempo limite excedido ao conectar ao servidor SMTP.")
        if isinstance(exc, ssl.SSLError):
            return MailDeliveryResult(False, "SMTP_SSL", "Falha na negociação SSL/TLS com o servidor SMTP.")
        if isinstance(exc, smtplib.SMTPConnectError):
            return MailDeliveryResult(False, "SMTP_CONNECT", "O servidor SMTP recusou a conexão.")
        if isinstance(exc, smtplib.SMTPException):
            return MailDeliveryResult(False, "SMTP_PROTOCOL", "Falha de protocolo durante a entrega SMTP.")
        return MailDeliveryResult(False, "SMTP_NETWORK", "Falha de rede ao conectar ao servidor SMTP.")

    def _base_message(self, *, recipient: str, subject: str) -> EmailMessage | None:
        if not self.enabled or not settings.smtp_from_email:
            return None
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
        message["To"] = recipient
        if settings.smtp_reply_to:
            message["Reply-To"] = settings.smtp_reply_to
        return message

    def _send(self, message: EmailMessage | None, *, purpose: str) -> MailDeliveryResult:
        if message is None or not settings.smtp_host:
            logger.warning("SMTP não configurado; %s não foi enviado", purpose)
            return MailDeliveryResult(False, "SMTP_NOT_CONFIGURED", "SMTP não está configurado no container da API.")
        client_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
        try:
            context = ssl.create_default_context()
            with client_class(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=context,
            ) if settings.smtp_use_ssl else client_class(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as client:
                if settings.smtp_use_tls and not settings.smtp_use_ssl:
                    client.starttls(context=context)
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password or "")
                client.send_message(message)
            return MailDeliveryResult(True)
        except (OSError, smtplib.SMTPException) as exc:
            logger.exception("Falha ao entregar %s via SMTP", purpose)
            return self._failure(exc)

    def send_test_message(self, *, recipient: str) -> MailDeliveryResult:
        message = self._base_message(recipient=recipient, subject="Teste de SMTP — Scheduler Pro")
        if message is not None:
            message.set_content(
                "Este é um teste de entrega SMTP do Scheduler Pro.\n\n"
                "Se esta mensagem chegou, servidor, autenticação e remetente estão operacionais."
            )
        return self._send(message, purpose="teste SMTP")

    def send_password_reset(
        self,
        *,
        recipient: str,
        reset_url: str,
        platform_access: bool,
    ) -> MailDeliveryResult:
        context_name = "Control Plane" if platform_access else "Scheduler Pro"
        message = self._base_message(
            recipient=recipient,
            subject=f"Redefinição de senha — {context_name}",
        )
        if message is not None:
            message.set_content(
                f"Recebemos uma solicitação para redefinir sua senha no {context_name}.\n\n"
                f"Acesse: {reset_url}\n\n"
                f"Validade: {settings.password_reset_ttl_minutes} minutos.\n"
                "O link é de uso único. Se você não solicitou a alteração, ignore esta mensagem."
            )
            message.add_alternative(
                "<html><body style='font-family:Arial,sans-serif;color:#10233f'>"
                "<h2>Redefinição de senha</h2>"
                f"<p>Recebemos uma solicitação para redefinir sua senha no {escape(context_name)}.</p>"
                f"<p><a href='{escape(reset_url, quote=True)}' style='display:inline-block;padding:12px 18px;"
                "background:#0b9fea;color:#fff;text-decoration:none;border-radius:8px'>Redefinir minha senha</a></p>"
                f"<p>O link é válido por {settings.password_reset_ttl_minutes} minutos e pode ser usado uma única vez.</p>"
                "<p>Se você não solicitou a alteração, ignore esta mensagem.</p>"
                "</body></html>",
                subtype="html",
            )
        return self._send(message, purpose="recuperação de senha")

    def send_tenant_welcome(
        self,
        *,
        recipient: str,
        tenant_name: str,
        tenant_code: str,
        temporary_password: str,
        login_url: str,
    ) -> MailDeliveryResult:
        message = self._base_message(
            recipient=recipient,
            subject=f"Seu acesso ao Scheduler Pro — {tenant_name}",
        )
        if message is not None:
            message.set_content(
                f"Seu ambiente {tenant_name} foi provisionado no Scheduler Pro.\n\n"
                f"Código do tenant: {tenant_code}\n"
                f"Usuário administrador: {recipient}\n"
                f"Senha inicial: {temporary_password}\n"
                f"Acesso: {login_url}\n\n"
                "Altere a senha após o primeiro acesso. Não compartilhe esta mensagem."
            )
            message.add_alternative(
                "<html><body style='font-family:Arial,sans-serif;color:#10233f'>"
                f"<h2>Bem-vindo ao {escape(tenant_name)}</h2>"
                "<p>Seu ambiente no Scheduler Pro está pronto.</p>"
                f"<p><strong>Código do tenant:</strong> {escape(tenant_code)}<br>"
                f"<strong>Usuário administrador:</strong> {escape(recipient)}<br>"
                f"<strong>Senha inicial:</strong> <code>{escape(temporary_password)}</code></p>"
                f"<p><a href='{escape(login_url, quote=True)}' style='display:inline-block;padding:12px 18px;"
                "background:#0b9fea;color:#fff;text-decoration:none;border-radius:8px'>Acessar Scheduler Pro</a></p>"
                "<p>Por segurança, altere sua senha depois do primeiro acesso e não compartilhe esta mensagem.</p>"
                "</body></html>",
                subtype="html",
            )
        return self._send(message, purpose="credenciais iniciais do tenant")


mail_delivery = MailDeliveryService()

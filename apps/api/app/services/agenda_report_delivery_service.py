from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
from datetime import UTC, date, datetime, time, timedelta
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.tenant_context import TenantContext
from app.services.file_service import TenantFileService
from app.services.phone_normalization import PhoneNormalizationService

PERIODS = {"day", "week", "month", "quarter", "semester", "year"}
PERIOD_LABELS = {
    "day": "diário",
    "week": "semanal",
    "month": "mensal",
    "quarter": "trimestral",
    "semester": "semestral",
    "year": "anual",
}


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Bahia")


def period_bounds(period: str, anchor: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    if period == "day":
        start_date, end_date = anchor, anchor + timedelta(days=1)
    elif period == "week":
        start_date = anchor - timedelta(days=anchor.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == "month":
        start_date = anchor.replace(day=1)
        end_date = (
            start_date.replace(year=start_date.year + 1, month=1)
            if start_date.month == 12
            else start_date.replace(month=start_date.month + 1)
        )
    elif period == "quarter":
        month = ((anchor.month - 1) // 3) * 3 + 1
        start_date = anchor.replace(month=month, day=1)
        next_month = month + 3
        end_date = (
            start_date.replace(year=start_date.year + 1, month=next_month - 12)
            if next_month > 12
            else start_date.replace(month=next_month)
        )
    elif period == "semester":
        month = 1 if anchor.month <= 6 else 7
        start_date = anchor.replace(month=month, day=1)
        end_date = (
            start_date.replace(month=7)
            if month == 1
            else start_date.replace(year=start_date.year + 1, month=1)
        )
    elif period == "year":
        start_date = anchor.replace(month=1, day=1)
        end_date = start_date.replace(year=start_date.year + 1)
    else:
        raise APIError("AGENDA_REPORT_PERIOD_INVALID", "Período de relatório inválido.", 422)
    return (
        datetime.combine(start_date, time.min, tzinfo=timezone).astimezone(UTC),
        datetime.combine(end_date, time.min, tzinfo=timezone).astimezone(UTC),
    )


def previous_period_anchor(period: str, today: date) -> date:
    if period == "day":
        return today - timedelta(days=1)
    if period == "week":
        current_monday = today - timedelta(days=today.weekday())
        return current_monday - timedelta(days=1)
    if period == "month":
        return today.replace(day=1) - timedelta(days=1)
    if period == "quarter":
        current_month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=current_month, day=1) - timedelta(days=1)
    if period == "semester":
        current_month = 1 if today.month <= 6 else 7
        return today.replace(month=current_month, day=1) - timedelta(days=1)
    if period == "year":
        return today.replace(month=1, day=1) - timedelta(days=1)
    raise APIError("AGENDA_REPORT_PERIOD_INVALID", "Período de relatório inválido.", 422)


def _due_on(period: str, now: datetime, hour: int) -> bool:
    if now.hour != hour:
        return False
    if period == "day":
        return True
    if period == "week":
        return now.weekday() == 0
    if period == "month":
        return now.day == 1
    if period == "quarter":
        return now.day == 1 and now.month in {1, 4, 7, 10}
    if period == "semester":
        return now.day == 1 and now.month in {1, 7}
    if period == "year":
        return now.day == 1 and now.month == 1
    return False


def _safe_pdf_text(value: object) -> str:
    return str(value or "").encode("latin-1", "replace").decode("latin-1")


def minimal_pdf(lines: list[str]) -> bytes:
    """Generate a compact, dependency-free PDF for management summaries."""
    escaped: list[str] = []
    for raw in lines[:55]:
        value = _safe_pdf_text(raw).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        escaped.append(value)
    commands = ["BT", "/F1 10 Tf", "50 790 Td", "13 TL"]
    for index, line in enumerate(escaped):
        if index:
            commands.append("T*")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


def sign_report_token(tenant_id: str, key: str, content_type: str, expires_at: int) -> str:
    payload = json.dumps(
        {"tenant_id": tenant_id, "key": key, "type": content_type, "exp": expires_at},
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(settings.app_secret_key.encode(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_report_token(token: str, tenant_id: str) -> dict[str, Any]:
    try:
        encoded, signature_value = token.split(".", 1)
        signature = base64.urlsafe_b64decode(signature_value + "=" * (-len(signature_value) % 4))
        expected = hmac.new(settings.app_secret_key.encode(), encoded.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload_raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(payload_raw)
        if str(payload.get("tenant_id")) != tenant_id:
            raise ValueError("tenant")
        if int(payload.get("exp") or 0) < int(datetime.now(UTC).timestamp()):
            raise APIError("AGENDA_REPORT_LINK_EXPIRED", "Este link de relatório expirou.", 410)
        return dict(payload)
    except APIError:
        raise
    except Exception as exc:
        raise APIError("AGENDA_REPORT_LINK_INVALID", "Link de relatório inválido.", 404) from exc


class AgendaReportDeliveryService:
    def __init__(self, session: AsyncSession, context: TenantContext) -> None:
        self.session = session
        self.context = context
        self.timezone = _timezone(context.timezone)

    async def summary(self, period: str, anchor: date) -> dict[str, Any]:
        start, end = period_bounds(period, anchor, self.timezone)
        rows = (
            await self.session.execute(
                text(
                    """
                    select a.starts_at, a.status, a.customer_id::text,
                           c.name as customer_name, s.name as service_name,
                           coalesce(s.price, 0) as price,
                           p.name as professional_name
                    from appointments a
                    join customers c on c.id=a.customer_id
                    left join services s on s.id=a.service_id
                    join professionals p on p.id=a.professional_id
                    where a.starts_at >= :start and a.starts_at < :end
                    order by a.starts_at
                    """
                ),
                {"start": start, "end": end},
            )
        ).mappings().all()
        statuses: dict[str, int] = {}
        services: dict[str, int] = {}
        professionals: dict[str, int] = {}
        curve: dict[str, int] = {}
        customers: set[str] = set()
        revenue = 0.0
        for row in rows:
            status = str(row["status"])
            statuses[status] = statuses.get(status, 0) + 1
            service_name = str(row["service_name"] or "Sem serviço")
            services[service_name] = services.get(service_name, 0) + 1
            professional_name = str(row["professional_name"] or "Agenda geral")
            professionals[professional_name] = professionals.get(professional_name, 0) + 1
            customers.add(str(row["customer_id"]))
            local_day = row["starts_at"].astimezone(self.timezone).date().isoformat()
            curve[local_day] = curve.get(local_day, 0) + 1
            if status not in {"CANCELLED", "NO_SHOW"}:
                revenue += float(row["price"] or 0)
        total = len(rows)
        completed = statuses.get("COMPLETED", 0)
        cancelled = statuses.get("CANCELLED", 0)
        no_show = statuses.get("NO_SHOW", 0)
        attendance_base = max(1, total - cancelled)
        return {
            "period": period,
            "anchor": anchor.isoformat(),
            "range": {"starts_at": start.isoformat(), "ends_at": end.isoformat()},
            "synthetic": {
                "appointments": total,
                "unique_customers": len(customers),
                "completed": completed,
                "cancelled": cancelled,
                "no_show": no_show,
                "estimated_revenue": round(revenue, 2),
                "completion_rate": round(completed * 100 / attendance_base, 2),
                "no_show_rate": round(no_show * 100 / attendance_base, 2),
            },
            "analytical": {
                "curve": [{"date": key, "appointments": curve[key]} for key in sorted(curve)],
                "statuses": [{"status": key, "count": value} for key, value in sorted(statuses.items(), key=lambda item: (-item[1], item[0]))],
                "services": [{"name": key, "count": value} for key, value in sorted(services.items(), key=lambda item: (-item[1], item[0]))],
                "professionals": [{"name": key, "count": value} for key, value in sorted(professionals.items(), key=lambda item: (-item[1], item[0]))],
            },
        }

    def _html(self, summary: dict[str, Any]) -> bytes:
        synthetic = summary["synthetic"]
        curve = summary["analytical"]["curve"]
        services = summary["analytical"]["services"]
        period = PERIOD_LABELS.get(str(summary["period"]), str(summary["period"]))
        bars = "".join(
            f"<tr><td>{html.escape(str(item['date']))}</td><td>{int(item['appointments'])}</td></tr>"
            for item in curve
        ) or "<tr><td colspan='2'>Sem atendimentos no período.</td></tr>"
        service_rows = "".join(
            f"<tr><td>{html.escape(str(item['name']))}</td><td>{int(item['count'])}</td></tr>"
            for item in services
        ) or "<tr><td colspan='2'>Sem serviços no período.</td></tr>"
        body = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Relatório da Agenda</title><style>body{{font-family:Inter,Arial,sans-serif;margin:0;background:#f4f7fb;color:#17243a}}main{{max-width:980px;margin:30px auto;padding:24px}}header{{padding:28px;border-radius:22px;background:#102544;color:#fff}}header p{{color:#cbd5e1}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}}.metric,section{{padding:18px;border:1px solid #dfe7f1;border-radius:16px;background:#fff}}.metric span{{display:block;color:#64748b;font-size:12px}}.metric strong{{font-size:26px}}section{{margin-top:14px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #edf2f7;text-align:left}}@media(max-width:640px){{main{{margin:0;padding:12px}}.metrics{{grid-template-columns:1fr 1fr}}}}</style></head><body><main><header><small>Scheduler Pro · Relatório gerencial</small><h1>Relatório {html.escape(period)}</h1><p>Referência: {html.escape(str(summary['anchor']))}</p></header><div class='metrics'><div class='metric'><span>Agendamentos</span><strong>{synthetic['appointments']}</strong></div><div class='metric'><span>Clientes únicos</span><strong>{synthetic['unique_customers']}</strong></div><div class='metric'><span>Concluídos</span><strong>{synthetic['completed']}</strong></div><div class='metric'><span>Cancelados</span><strong>{synthetic['cancelled']}</strong></div><div class='metric'><span>Não compareceu</span><strong>{synthetic['no_show']}</strong></div><div class='metric'><span>Receita estimada</span><strong>R$ {synthetic['estimated_revenue']:.2f}</strong></div></div><section><h2>Curva de atendimentos</h2><table><thead><tr><th>Data</th><th>Atendimentos</th></tr></thead><tbody>{bars}</tbody></table></section><section><h2>Serviços</h2><table><thead><tr><th>Serviço</th><th>Quantidade</th></tr></thead><tbody>{service_rows}</tbody></table></section></main></body></html>"""
        return body.encode("utf-8")

    def _pdf_lines(self, summary: dict[str, Any]) -> list[str]:
        s = summary["synthetic"]
        period = PERIOD_LABELS.get(str(summary["period"]), str(summary["period"]))
        lines = [
            "Scheduler Pro - Relatorio gerencial da Agenda",
            f"Periodo: {period} | referencia: {summary['anchor']}",
            "",
            f"Agendamentos: {s['appointments']}",
            f"Clientes unicos: {s['unique_customers']}",
            f"Concluidos: {s['completed']}",
            f"Cancelados: {s['cancelled']}",
            f"Nao compareceu: {s['no_show']}",
            f"Receita estimada: R$ {s['estimated_revenue']:.2f}",
            f"Taxa de conclusao: {s['completion_rate']}%",
            f"Taxa de nao comparecimento: {s['no_show_rate']}%",
            "",
            "Curva de atendimentos:",
        ]
        lines.extend(
            f"  {item['date']}: {item['appointments']} atendimento(s)"
            for item in summary["analytical"]["curve"][:20]
        )
        lines.append("")
        lines.append("Servicos:")
        lines.extend(
            f"  {item['name']}: {item['count']}"
            for item in summary["analytical"]["services"][:15]
        )
        return lines

    def _public_url(self, key: str, content_type: str, *, days: int = 45) -> str:
        expiry = int((datetime.now(UTC) + timedelta(days=days)).timestamp())
        token = sign_report_token(self.context.tenant_id, key, content_type, expiry)
        scheme = "http" if self.context.hostname in {"localhost", "127.0.0.1"} else "https"
        return f"{scheme}://{self.context.hostname}/api/v1/public/agenda-report/{token}"

    async def generate(self, period: str, anchor: date, format_mode: str) -> dict[str, Any]:
        summary = await self.summary(period, anchor)
        stamp = f"{period}-{anchor.isoformat()}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        files = TenantFileService(self.context)
        result: dict[str, Any] = {"summary": summary, "online_url": None, "pdf_url": None}
        if format_mode in {"link", "link_pdf"}:
            key = f"reports/agenda/{stamp}.html"
            await files.upload(key, BytesIO(self._html(summary)), "text/html; charset=utf-8")
            result["online_url"] = self._public_url(key, "text/html; charset=utf-8")
        if format_mode in {"pdf", "link_pdf"}:
            key = f"reports/agenda/{stamp}.pdf"
            await files.upload(key, BytesIO(minimal_pdf(self._pdf_lines(summary))), "application/pdf")
            result["pdf_url"] = self._public_url(key, "application/pdf")
        return result

    async def _queue_delivery(self, schedule: dict[str, Any], generated: dict[str, Any]) -> int:
        period = str(schedule.get("period") or "month")
        label = PERIOD_LABELS.get(period, period)
        subject = f"Scheduler Pro — relatório {label} da Agenda"
        lines = [subject]
        if generated.get("online_url"):
            lines.append(f"Visualizar relatório online: {generated['online_url']}")
        if generated.get("pdf_url"):
            lines.append(f"Abrir relatório em PDF: {generated['pdf_url']}")
        message = "\n\n".join(lines)
        channels = schedule.get("delivery_channels")
        channel_list = channels if isinstance(channels, list) else []
        queued = 0
        normalizer = await PhoneNormalizationService.from_session(self.session)
        for channel in channel_list:
            recipient = ""
            if channel == "email":
                recipient = str(schedule.get("email") or "").strip()
            elif channel == "whatsapp":
                raw = str(schedule.get("whatsapp") or "").strip()
                recipient = normalizer.normalize(raw, required=False) or ""
            if not recipient:
                continue
            await self.session.execute(
                text(
                    """
                    insert into notification_jobs(
                      appointment_id, channel, recipient, template_key,
                      payload, scheduled_at, status
                    ) values(
                      null, :channel, :recipient, 'agenda_management_report',
                      cast(:payload as jsonb), now(), 'PENDING'
                    )
                    """
                ),
                {
                    "channel": channel,
                    "recipient": recipient,
                    "payload": json.dumps(
                        {"message": message, "subject": subject},
                        ensure_ascii=False,
                    ),
                },
            )
            queued += 1
        return queued

    async def process_due_schedules(self) -> dict[str, int]:
        raw = await self.session.scalar(
            text("select value from tenant_settings where key='agenda_report_schedules' limit 1")
        )
        schedules = raw if isinstance(raw, list) else []
        now_local = datetime.now(self.timezone)
        generated_count = 0
        queued_count = 0
        for item in schedules:
            if not isinstance(item, dict) or not bool(item.get("enabled")):
                continue
            period = str(item.get("period") or "month")
            if period not in PERIODS:
                continue
            hour = max(0, min(23, int(item.get("hour") or 8)))
            if not _due_on(period, now_local, hour):
                continue
            signature = now_local.date().isoformat()
            last_key = f"agenda_report_last_{period}"
            last = await self.session.scalar(
                text("select value from tenant_settings where key=:key limit 1"),
                {"key": last_key},
            )
            if str(last or "") == signature:
                continue
            anchor = previous_period_anchor(period, now_local.date())
            generated = await self.generate(period, anchor, str(item.get("format") or "link"))
            queued_count += await self._queue_delivery(item, generated)
            await self.session.execute(
                text(
                    """
                    insert into tenant_settings(key, value, updated_at)
                    values(:key, cast(:value as jsonb), now())
                    on conflict(key) do update set value=excluded.value, updated_at=now()
                    """
                ),
                {"key": last_key, "value": json.dumps(signature)},
            )
            generated_count += 1
        await self.session.commit()
        return {"generated": generated_count, "queued": queued_count}

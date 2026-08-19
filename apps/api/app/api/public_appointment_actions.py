from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, get_tenant_context, get_tenant_session
from app.core.errors import APIError
from app.core.tenant_context import TenantContext
from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.branding_service import BrandingService
from app.services.realtime_service import RealtimeEventService
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/a", tags=["Public Appointment Action"])

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _color(value: object, fallback: str) -> str:
    candidate = str(value or "").strip()
    return candidate if _HEX.fullmatch(candidate) else fallback


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Bahia")


def _date(value: object, timezone: ZoneInfo) -> str:
    if not isinstance(value, datetime):
        return "—"
    return value.astimezone(timezone).strftime("%d/%m/%Y às %H:%M")


def _dict_value(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _result_message(snapshot: dict[str, Any]) -> tuple[str, str]:
    state = str(snapshot.get("state") or "PENDING").upper()
    status = str(snapshot.get("status") or "").upper()
    if state == "CONFIRMED" or status == "CONFIRMED":
        return "Agendamento confirmado", "Obrigado! Sua confirmação já foi registrada."
    if state == "CANCELLED" or status == "CANCELLED":
        return (
            "Agendamento cancelado",
            "O horário foi liberado e sua resposta já foi registrada.",
        )
    if state == "EXPIRED" or snapshot.get("deadline_expired"):
        return (
            "Prazo de confirmação encerrado",
            "Este horário já não pode ser confirmado por este link.",
        )
    return "", ""


def _render_page(
    *,
    snapshot: dict[str, Any] | None,
    page: dict[str, str],
    branding: dict[str, Any],
    context: TenantContext,
    token: str,
    flash_title: str = "",
    flash_message: str = "",
    flash_kind: str = "",
) -> HTMLResponse:
    app: dict[str, Any] = _dict_value(branding, "app")
    assets: dict[str, Any] = _dict_value(branding, "assets")
    theme: dict[str, Any] = _dict_value(branding, "theme")
    colors: dict[str, Any] = _dict_value(theme, "colors")

    app_name = html.escape(
        str(app.get("public_name") or app.get("name") or context.slug)
    )
    primary = _color(colors.get("primary"), "#2563eb")
    accent = _color(colors.get("accent"), "#06b6d4")
    background = _color(colors.get("background"), "#f8fafc")
    text_color = _color(colors.get("text"), "#0f172a")
    logo_url = str(assets.get("logo_url") or "").strip()
    logo = (
        f'<img class="logo" src="{html.escape(logo_url, quote=True)}" alt="{app_name}">'
        if logo_url
        else f'<div class="logo-fallback">{html.escape(app_name[:2].upper())}</div>'
    )

    details = ""
    actions = ""
    status_block = ""
    timezone = _timezone(context.timezone)
    if snapshot is not None:
        customer = html.escape(str(snapshot.get("customer_name") or "Cliente"))
        service = html.escape(str(snapshot.get("service_name") or "Atendimento"))
        professional = html.escape(str(snapshot.get("professional_name") or "—"))
        starts_at = html.escape(_date(snapshot.get("starts_at"), timezone))
        deadline = html.escape(
            _date(snapshot.get("confirmation_deadline"), timezone)
        )
        details = f"""
          <div class="appointment-card">
            <div><span>Cliente</span><strong>{customer}</strong></div>
            <div><span>Serviço</span><strong>{service}</strong></div>
            <div><span>Profissional</span><strong>{professional}</strong></div>
            <div><span>Data e horário</span><strong>{starts_at}</strong></div>
            <div class="deadline"><span>Responder até</span><strong>{deadline}</strong></div>
          </div>
        """
        if bool(snapshot.get("can_respond")):
            actions = f"""
              <div class="actions">
                <form method="post" action="/a/{html.escape(token, quote=True)}/confirm">
                  <button class="confirm" type="submit">{html.escape(page['confirmation_confirm_label'])}</button>
                </form>
                <form method="post" action="/a/{html.escape(token, quote=True)}/cancel" onsubmit="return confirm('Deseja realmente cancelar este agendamento?')">
                  <button class="cancel" type="submit">{html.escape(page['confirmation_cancel_label'])}</button>
                </form>
              </div>
            """
        elif not flash_title:
            state_title, state_message = _result_message(snapshot)
            if state_title:
                status_block = (
                    f'<div class="flash neutral"><strong>{html.escape(state_title)}</strong>'
                    f'<p>{html.escape(state_message)}</p></div>'
                )

    if flash_title:
        kind = (
            flash_kind
            if flash_kind in {"success", "danger", "neutral"}
            else "neutral"
        )
        status_block = (
            f'<div class="flash {kind}"><strong>{html.escape(flash_title)}</strong>'
            f'<p>{html.escape(flash_message)}</p></div>'
        )

    title = html.escape(page["confirmation_page_title"])
    message = html.escape(page["confirmation_page_message"])
    document = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{title} — {app_name}</title>
  <style>
    :root{{--primary:{primary};--accent:{accent};--bg:{background};--text:{text_color}}}
    *{{box-sizing:border-box}}
    body{{margin:0;min-height:100vh;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;background:linear-gradient(155deg,#f8fbff,#eef5ff 52%,#f8fafc);color:#0f172a;display:grid;place-items:center;padding:24px}}
    .shell{{width:min(680px,100%);background:#fff;border:1px solid #e2e8f0;border-radius:28px;box-shadow:0 28px 80px rgba(15,23,42,.12);overflow:hidden}}
    .hero{{padding:30px 34px 26px;background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff}}
    .brand{{display:flex;align-items:center;gap:12px;margin-bottom:30px}}.logo{{max-width:160px;max-height:54px;object-fit:contain;background:#fff;border-radius:12px;padding:6px}}.logo-fallback{{width:48px;height:48px;border-radius:14px;background:#fff;color:var(--primary);display:grid;place-items:center;font-weight:900}}
    .brand strong{{font-size:17px}}h1{{margin:0;font-size:clamp(30px,6vw,45px);line-height:1.05;letter-spacing:-.04em}}.hero p{{margin:12px 0 0;max-width:560px;line-height:1.6;color:rgba(255,255,255,.88)}}
    main{{padding:30px 34px 34px}}.appointment-card{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:22px}}.appointment-card>div{{border:1px solid #e2e8f0;border-radius:16px;padding:14px;background:#f8fafc}}.appointment-card span,.appointment-card strong{{display:block}}.appointment-card span{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;font-weight:800;margin-bottom:5px}}.appointment-card strong{{font-size:14px;line-height:1.35}}.appointment-card .deadline{{grid-column:1/-1;background:#fff7ed;border-color:#fed7aa}}
    .actions{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}form{{margin:0}}button{{width:100%;min-height:50px;border-radius:14px;border:0;font:inherit;font-weight:900;cursor:pointer;padding:12px}}button.confirm{{background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;box-shadow:0 10px 24px rgba(37,99,235,.2)}}button.cancel{{background:#fff;border:1px solid #fecaca;color:#b91c1c}}
    .flash{{border-radius:16px;padding:17px 18px;margin-bottom:20px}}.flash strong,.flash p{{display:block;margin:0}}.flash p{{margin-top:5px;line-height:1.5;font-size:13px}}.flash.success{{background:#dcfce7;color:#166534}}.flash.danger{{background:#fee2e2;color:#991b1b}}.flash.neutral{{background:#eff6ff;color:#1e40af}}
    .foot{{text-align:center;color:#94a3b8;font-size:11px;margin-top:22px}}
    @media(max-width:560px){{body{{padding:10px}}.shell{{border-radius:20px}}.hero,main{{padding:24px 20px}}.appointment-card,.actions{{grid-template-columns:1fr}}.appointment-card .deadline{{grid-column:auto}}}}
  </style>
</head>
<body>
  <section class="shell">
    <header class="hero"><div class="brand">{logo}<strong>{app_name}</strong></div><h1>{title}</h1><p>{message}</p></header>
    <main>{status_block}{details}{actions}<div class="foot">Página segura de confirmação • Scheduler Pro</div></main>
  </section>
</body>
</html>"""
    return HTMLResponse(document)


async def _content(
    token: str,
    context: TenantContext,
    tenant_session: AsyncSession,
    platform_session: AsyncSession,
) -> tuple[
    AppointmentConfirmationService,
    dict[str, Any],
    dict[str, str],
    dict[str, Any],
]:
    service = AppointmentConfirmationService(tenant_session)
    current_snapshot = await service.snapshot(token)
    page = await service.page_settings()
    branding = await BrandingService(platform_session).manifest_for_context(context)
    return service, current_snapshot, page, branding


@router.get("/{token}", response_class=HTMLResponse)
async def appointment_action_page(
    token: str,
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> HTMLResponse:
    try:
        _, current_snapshot, page, branding = await _content(
            token,
            context,
            tenant_session,
            platform_session,
        )
        return _render_page(
            snapshot=current_snapshot,
            page=page,
            branding=branding,
            context=context,
            token=token,
        )
    except APIError as exc:
        page = await AppointmentConfirmationService(tenant_session).page_settings()
        branding = await BrandingService(platform_session).manifest_for_context(context)
        return _render_page(
            snapshot=None,
            page=page,
            branding=branding,
            context=context,
            token=token,
            flash_title="Link indisponível",
            flash_message=exc.message,
            flash_kind="danger",
        )


@router.post("/{token}/{action}", response_class=HTMLResponse)
async def appointment_action_submit(
    token: str,
    action: str,
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> HTMLResponse:
    service = AppointmentConfirmationService(tenant_session)
    page = await service.page_settings()
    branding = await BrandingService(platform_session).manifest_for_context(context)
    try:
        before = await service.snapshot(token)
        response_snapshot = await service.respond(token, action)
        confirmed = (
            str(response_snapshot.get("state") or "").upper() == "CONFIRMED"
        )
        before_state = str(before.get("state") or "").upper()
        appointment_id = str(response_snapshot.get("appointment_id") or "")
        if before_state == "PENDING" and appointment_id:
            event = await RealtimeEventService(tenant_session).emit_appointment(
                appointment_id,
                (
                    "appointment.customer_confirmed"
                    if confirmed
                    else "appointment.customer_cancelled"
                ),
                actor="customer-public-link",
            )
            event_id = str(event.get("id") or "") if event else ""
            if event_id:
                celery_app.send_task(
                    "app.workers.tasks.dispatch_realtime_push",
                    args=[context.tenant_id, event_id],
                    queue="notifications",
                )
        return _render_page(
            snapshot=response_snapshot,
            page=page,
            branding=branding,
            context=context,
            token=token,
            flash_title=(
                "Agendamento confirmado" if confirmed else "Agendamento cancelado"
            ),
            flash_message=(
                "Sua confirmação foi registrada com sucesso."
                if confirmed
                else "Seu cancelamento foi registrado e o horário foi liberado."
            ),
            flash_kind="success" if confirmed else "neutral",
        )
    except APIError as exc:
        fallback_snapshot: dict[str, Any] | None = None
        try:
            fallback_snapshot = await service.snapshot(token)
        except APIError:
            pass
        return _render_page(
            snapshot=fallback_snapshot,
            page=page,
            branding=branding,
            context=context,
            token=token,
            flash_title="Não foi possível registrar a resposta",
            flash_message=exc.message,
            flash_kind="danger",
        )

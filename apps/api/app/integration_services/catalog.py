"""Explicit machine API surface. Adding a route never silently grants a new scope."""

from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import Scope

TENANT_RESOURCES = {
    "appointments": "Agendamentos",
    "appointment-confirmations": "Confirmações",
    "agenda": "Agenda e relatórios",
    "check-in": "Check-in",
    "customers": "Clientes",
    "services": "Serviços",
    "professionals": "Profissionais",
    "schedule": "Horários e bloqueios",
    "availability": "Disponibilidade",
    "notifications": "Notificações",
    "landing-pages": "Páginas públicas",
    "files": "Arquivos",
    "settings": "Configurações",
    "observability": "Observabilidade",
    "downloads": "Distribuição",
    "experience": "Editor visual",
    "branding": "Identidade visual",
    "realtime": "Eventos e notificações push",
    "integrations/whatsapp": "ARGWS WhatsApp API",
    "integrations/services": "API Services e Webhook Services",
}
PLATFORM_RESOURCES = {
    "tenants": "Empresas",
    "domains": "Domínios",
    "provisioning": "Provisionamento",
    "dashboard": "Indicadores",
    "feature-flags": "Recursos",
    "integrations": "Integrações",
    "audit": "Auditoria",
    "tenant-management": "Gestão de empresas",
    "tenant-support": "Suporte às empresas",
    "templates": "Modelos globais",
    "html-templates": "Modelos HTML",
    "access": "Acessos e permissões",
    "observability": "Observabilidade",
    "builds": "Distribuição",
}
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
TENANT_EVENTS = (
    "appointment",
    "customer",
    "service",
    "professional",
    "landing_page",
    "business_hour",
    "blocked_period",
    "notification",
)
PLATFORM_EVENTS = ("tenant", "domain", "provisioning", "build", "template")
APPOINTMENT_STATES = (
    "confirmed",
    "cancelled",
    "checked_in",
    "in_progress",
    "completed",
    "no_show",
    "rescheduled",
    "awaiting_confirmation",
    "pending",
)


def event_catalog(platform: bool) -> list[str]:
    events = [
        f"{item}.{action}"
        for item in (PLATFORM_EVENTS if platform else TENANT_EVENTS)
        for action in ("created", "updated", "deleted")
    ]
    if not platform:
        events += [f"appointment.{state}" for state in APPOINTMENT_STATES]
    return ["webhook.test", *sorted(events)]


def scope_for(path: str, method: str, platform: bool) -> str | None:
    prefix = "/api/v1/platform/" if platform else "/api/v1/"
    if not path.startswith(prefix):
        return None
    suffix = path[len(prefix) :].strip("/")
    resources = PLATFORM_RESOURCES if platform else TENANT_RESOURCES
    resource = next(
        (
            name
            for name in sorted(resources, key=len, reverse=True)
            if suffix == name or suffix.startswith(name + "/")
        ),
        None,
    )
    if resource is None:
        return None
    # Browser credentials, secret issuance and long-lived streams are not delegated.
    if (
        "/integrations/services/tokens" in path
        or path.endswith("/realtime/stream")
        or path.endswith("/resolve-outcome")
    ):
        return None
    verb = "read" if method.upper() in SAFE_METHODS else "write"
    return f"{resource.replace('/', '.')}.{verb}"


def scopes_catalog(platform: bool) -> list[dict[str, str]]:
    resources = PLATFORM_RESOURCES if platform else TENANT_RESOURCES
    return [
        {"key": f"{key.replace('/', '.')}.{verb}", "label": f"{label} — {title}"}
        for key, label in resources.items()
        for verb, title in (("read", "consultar"), ("write", "alterar"))
    ]


def _dependencies(route: APIRoute) -> set[str]:
    result: set[str] = set()
    pending = [route.dependant]
    while pending:
        item = pending.pop()
        result.add(getattr(item.call, "__name__", ""))
        pending.extend(item.dependencies)
    return result


def machine_route(route: APIRoute, platform: bool) -> bool:
    calls = _dependencies(route)
    # Privileged security lifecycle stays interactive. Never expose public handlers
    # merely because their path shares a protected resource prefix.
    if "require_super_admin" in calls:
        return False
    required = "get_current_platform_user" if platform else "get_current_tenant_user"
    return required in calls


def match_operation(app: FastAPI, scope: Scope, platform: bool) -> str | None:
    for route in app.routes:
        if isinstance(route, APIRoute):
            matched, _ = route.matches(scope)
            if matched == Match.FULL:
                return (
                    scope_for(route.path, scope["method"], platform)
                    if machine_route(route, platform)
                    else None
                )
    return None


def operation_catalog(app: FastAPI, platform: bool) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not machine_route(route, platform):
            continue
        for method in sorted(route.methods or []):
            permission = scope_for(route.path, method, platform)
            if permission:
                result.append(
                    {
                        "method": method,
                        "path": route.path,
                        "scope": permission,
                        "name": route.name,
                        "idempotency_required": method not in SAFE_METHODS,
                    }
                )
    return result

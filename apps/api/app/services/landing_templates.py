from __future__ import annotations

from typing import Any

# Catálogo legado mantido apenas como contrato de compatibilidade do serviço.
# Novos modelos são Template Packages V1 HTML first-class, instalados na
# biblioteca global pelo bootstrap e governados pelo Control Plane.
TEMPLATES: dict[str, dict[str, Any]] = {}


def list_templates() -> list[dict[str, Any]]:
    return []


def template_content(key: str) -> dict[str, Any]:
    raise KeyError(key)

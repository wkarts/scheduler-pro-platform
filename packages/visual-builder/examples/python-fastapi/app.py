from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)

app = FastAPI(title="ARGWS Visual Builder Example")
app.mount("/builder", StaticFiles(directory=PROJECT_ROOT), name="builder")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


def _file(slug: str, published: bool = False) -> Path:
    suffix = ".published.json" if published else ".draft.json"
    return DATA / f"{slug}{suffix}"


def _default() -> dict[str, Any]:
    return {
        "schema": "argws-visual-builder/v3",
        "version": 4,
        "title": "Landing Page FastAPI",
        "global_styles": {"primary": "#3151cf", "secondary": "#151c31", "accent": "#6d72ef", "background": "#ffffff", "text": "#1d273a", "heading_font": "Inter", "body_font": "Inter", "radius": 16},
        "seo": {"open_graph": {}, "twitter": {}, "structured_data": []},
        "project": {"capabilities": {}, "assets": {"fonts": [], "icons": [], "media": []}, "custom_code": [], "data_requirements": [], "i18n": {"default_locale": "pt-BR", "locales": ["pt-BR"], "translations": {}}, "permissions": {"roles": {}}, "collaboration": {"revision": 0}, "integrations": {}},
        "builder": {"schema": "argws-visual-builder/v3", "root_ids": [], "nodes": {}},
        "blocks": [],
    }


@app.get("/", response_class=HTMLResponse)
def editor() -> str:
    return (HERE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/pages/{slug}")
def page(slug: str) -> dict[str, Any]:
    path = _file(slug)
    document = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _default()
    return {"data": {"document": document}}


@app.post("/api/pages/{slug}/draft")
def draft(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") not in {"argws-visual-builder/v1", "argws-visual-builder/v2", "argws-visual-builder/v3"}:
        raise HTTPException(422, "Documento do builder inválido")
    _file(slug).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"data": {"saved": True}}


@app.post("/api/pages/{slug}/autosave")
def autosave(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    return draft(slug, payload)


@app.post("/api/pages/{slug}/publish")
def publish(slug: str) -> dict[str, Any]:
    source = _file(slug)
    if not source.exists():
        raise HTTPException(409, "Salve o rascunho antes de publicar")
    _file(slug, published=True).write_bytes(source.read_bytes())
    return {"data": {"published": True}}

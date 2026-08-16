import hmac
import os
from hashlib import sha256
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI, Header, HTTPException, Query

from app.core.config import settings

app = FastAPI(title="Scheduler Pro Docker Log Agent", docs_url=None, redoc_url=None, openapi_url=None)
DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
COMPOSE_PROJECT = os.getenv("LOG_AGENT_COMPOSE_PROJECT", "scheduler-pro")


def _token() -> str:
    return hmac.new(settings.app_secret_key.encode(), b"scheduler-pro-log-agent", sha256).hexdigest()


def _authorize(value: str | None) -> None:
    if not value or not hmac.compare_digest(value, _token()):
        raise HTTPException(status_code=403, detail="forbidden")


def _client() -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCKET)
    return httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=20.0)


def _decode_logs(content: bytes) -> list[dict[str, str]]:
    if not content:
        return []
    lines: list[tuple[str, str]] = []
    offset = 0
    multiplexed = len(content) >= 8 and content[0] in (0, 1, 2) and content[1:4] == b"\x00\x00\x00"
    if multiplexed:
        while offset + 8 <= len(content):
            stream_code = content[offset]
            size = int.from_bytes(content[offset + 4 : offset + 8], "big")
            offset += 8
            payload = content[offset : offset + size]
            offset += size
            stream = "stderr" if stream_code == 2 else "stdout"
            for raw in payload.decode("utf-8", errors="replace").splitlines():
                lines.append((stream, raw))
    else:
        for raw in content.decode("utf-8", errors="replace").splitlines():
            lines.append(("stdout", raw))

    result: list[dict[str, str]] = []
    for stream, raw in lines:
        timestamp = ""
        message = raw
        if " " in raw and "T" in raw[:32]:
            maybe_timestamp, remainder = raw.split(" ", 1)
            if maybe_timestamp.endswith("Z") or "+" in maybe_timestamp[10:]:
                timestamp, message = maybe_timestamp, remainder
        result.append({"timestamp": timestamp, "stream": stream, "message": message})
    return result


async def _project_containers() -> list[dict[str, Any]]:
    filters = '{"label":["com.docker.compose.project=' + COMPOSE_PROJECT.replace('"', '') + '"]}'
    async with _client() as client:
        response = await client.get("/containers/json", params={"all": "1", "filters": filters})
        response.raise_for_status()
        rows = response.json()
    result: list[dict[str, Any]] = []
    for row in rows:
        labels = row.get("Labels") or {}
        names = [str(item).lstrip("/") for item in row.get("Names") or []]
        result.append(
            {
                "id": str(row.get("Id", ""))[:12],
                "container_id": str(row.get("Id", "")),
                "name": names[0] if names else str(row.get("Id", ""))[:12],
                "service": labels.get("com.docker.compose.service"),
                "project": labels.get("com.docker.compose.project"),
                "image": row.get("Image"),
                "state": row.get("State"),
                "status": row.get("Status"),
            }
        )
    return sorted(result, key=lambda item: (str(item.get("service") or ""), str(item.get("name") or "")))


async def _resolve_container(identifier: str) -> dict[str, Any]:
    clean = identifier.strip().lstrip("/")
    for container in await _project_containers():
        if clean in {container["id"], container["container_id"], container["name"], container.get("service")}:
            return container
    raise HTTPException(status_code=404, detail="container not found in Scheduler Pro project")


@app.get("/health")
async def health(x_log_agent_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(x_log_agent_token)
    containers = await _project_containers()
    return {"ok": True, "project": COMPOSE_PROJECT, "containers": len(containers)}


@app.get("/containers")
async def containers(x_log_agent_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(x_log_agent_token)
    return {"containers": await _project_containers()}


@app.get("/logs")
async def logs(
    container: str = Query(min_length=1, max_length=180),
    tail: int = Query(default=500, ge=1, le=5000),
    since: int | None = Query(default=None, ge=0),
    search: str | None = Query(default=None, max_length=300),
    x_log_agent_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(x_log_agent_token)
    resolved = await _resolve_container(container)
    params: dict[str, str] = {"stdout": "1", "stderr": "1", "timestamps": "1", "tail": str(tail)}
    if since is not None:
        params["since"] = str(since)
    async with _client() as client:
        response = await client.get(f"/containers/{quote(resolved['container_id'], safe='')}/logs", params=params)
        response.raise_for_status()
    entries = _decode_logs(response.content)
    if search:
        needle = search.casefold()
        entries = [entry for entry in entries if needle in entry["message"].casefold()]
    return {"container": resolved, "entries": entries, "count": len(entries)}

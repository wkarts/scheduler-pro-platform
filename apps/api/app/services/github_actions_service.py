import os
from typing import Any

import httpx

from app.core.errors import APIError


class GitHubActionsService:
    def __init__(self) -> None:
        self.api_base = os.getenv("GITHUB_ACTIONS_API_BASE_URL", "https://api.github.com").rstrip("/")
        self.repository = os.getenv("GITHUB_ACTIONS_REPOSITORY", "wkarts/scheduler-pro-platform").strip()
        self.token = os.getenv("GITHUB_ACTIONS_TOKEN", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.repository and self.token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    async def dispatch(self, workflow_file: str, *, ref: str = "main", inputs: dict[str, str] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise APIError(
                "GITHUB_ACTIONS_NOT_CONFIGURED",
                "GitHub Actions não configurado no Control Plane.",
                424,
                {"hint": "Configure GITHUB_ACTIONS_TOKEN com Actions:Write e GITHUB_ACTIONS_REPOSITORY."},
            )
        url = f"{self.api_base}/repos/{self.repository}/actions/workflows/{workflow_file}/dispatches"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=self._headers(), json={"ref": ref, "inputs": inputs or {}})
        if response.status_code != 204:
            try:
                payload = response.json()
            except ValueError:
                payload = {"raw": response.text}
            raise APIError(
                "GITHUB_ACTIONS_DISPATCH_FAILED",
                "Falha ao disparar workflow de build.",
                424,
                {"status_code": response.status_code, "response": payload, "workflow": workflow_file},
            )
        return {"dispatched": True, "workflow": workflow_file, "ref": ref, "repository": self.repository, "inputs": inputs or {}}

    async def latest_runs(self, workflow_file: str, *, branch: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        params: dict[str, Any] = {"event": "workflow_dispatch", "per_page": min(max(limit, 1), 50)}
        if branch:
            params["branch"] = branch
        url = f"{self.api_base}/repos/{self.repository}/actions/workflows/{workflow_file}/runs"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._headers(), params=params)
        if response.status_code >= 400:
            return []
        payload = response.json()
        return list(payload.get("workflow_runs", [])) if isinstance(payload, dict) else []

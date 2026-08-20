from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.errors import APIError


class DistributionArtifactService:
    """Mirror universal release artifacts into the platform S3/MinIO bucket.

    GitHub is an upstream source only. Tenant clients never receive a GitHub asset
    URL; downloads are served from the Scheduler Pro internal distribution bucket.
    """

    latest_key = "distribution/manifest/latest.json"

    def __init__(self) -> None:
        self.bucket = os.getenv("DISTRIBUTION_BUCKET", "scheduler-distribution").strip() or "scheduler-distribution"
        self.source_repository = os.getenv("GITHUB_ACTIONS_REPOSITORY", "wkarts/scheduler-pro-platform").strip()
        self.source_token = os.getenv("GITHUB_ACTIONS_TOKEN", "").strip()
        self.source_api_base = os.getenv("GITHUB_ACTIONS_API_BASE_URL", "https://api.github.com").rstrip("/")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    @staticmethod
    def _asset_target(name: str) -> tuple[str, str] | None:
        lower = name.lower()
        if not lower.startswith("scheduler-pro-client-"):
            return None
        if "desktop-windows" in lower and lower.endswith(".tar.gz"):
            return "desktop-windows", "installer-bundle"
        if "desktop-linux" in lower and lower.endswith(".tar.gz"):
            return "desktop-linux", "installer-bundle"
        if "desktop-macos" in lower and lower.endswith(".tar.gz"):
            return "desktop-macos", "installer-bundle"
        if "-android-" in lower and lower.endswith(".apk"):
            return "android", "apk"
        if "-ios-" in lower and lower.endswith(".ipa"):
            return "ios", "ipa-unsigned"
        return None

    async def ensure_bucket(self) -> None:
        def ensure() -> None:
            try:
                self.s3.head_bucket(Bucket=self.bucket)
                return
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code") or "")
                status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
                if code not in {"404", "NoSuchBucket", "NotFound"} and status not in {404, 0}:
                    raise
            try:
                self.s3.create_bucket(Bucket=self.bucket)
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code") or "") not in {
                    "BucketAlreadyOwnedByYou",
                    "BucketAlreadyExists",
                }:
                    raise

        try:
            await asyncio.to_thread(ensure)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError(
                "DISTRIBUTION_STORAGE_UNAVAILABLE",
                "Storage interno de aplicativos indisponível.",
                424,
                {"error": str(exc)},
            ) from exc

    def _source_headers(self, *, binary: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/octet-stream" if binary else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "scheduler-pro-artifact-sync",
        }
        if self.source_token:
            headers["Authorization"] = f"Bearer {self.source_token}"
        return headers

    async def fetch_latest_release(self) -> dict[str, Any]:
        if not self.source_repository:
            raise APIError("DISTRIBUTION_REPOSITORY_MISSING", "Origem de releases não configurada.", 424)
        url = f"{self.source_api_base}/repos/{self.source_repository}/releases/latest"
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(url, headers=self._source_headers())
        except httpx.HTTPError as exc:
            raise APIError("DISTRIBUTION_SOURCE_UNAVAILABLE", "Origem de aplicativos indisponível.", 424) from exc
        if response.status_code >= 400:
            raise APIError(
                "DISTRIBUTION_SOURCE_UNAVAILABLE",
                "Não foi possível consultar a release mais recente.",
                424,
                {"status_code": response.status_code},
            )
        return dict(response.json())

    async def read_latest_manifest(self, *, required: bool = True) -> dict[str, Any] | None:
        try:
            result = await asyncio.to_thread(self.s3.get_object, Bucket=self.bucket, Key=self.latest_key)
            raw = await asyncio.to_thread(result["Body"].read)
            return dict(json.loads(raw.decode("utf-8")))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code") or "")
            if code in {"NoSuchKey", "NoSuchObject", "404", "NotFound"}:
                if required:
                    raise APIError(
                        "DISTRIBUTION_NOT_SYNCED",
                        "Os aplicativos ainda não foram espelhados para o storage interno.",
                        424,
                    ) from exc
                return None
            raise APIError("DISTRIBUTION_STORAGE_UNAVAILABLE", "Falha ao ler catálogo interno.", 424) from exc
        except (BotoCoreError, OSError, ValueError, json.JSONDecodeError) as exc:
            if required:
                raise APIError("DISTRIBUTION_STORAGE_UNAVAILABLE", "Falha ao ler catálogo interno.", 424) from exc
            return None

    @staticmethod
    def _manifest_matches_release(manifest: dict[str, Any] | None, release: dict[str, Any]) -> bool:
        if not manifest or manifest.get("release") != release.get("tag_name"):
            return False
        upstream = {
            str(item.get("name") or ""): int(item.get("size") or 0)
            for item in release.get("assets", [])
            if DistributionArtifactService._asset_target(str(item.get("name") or "")) is not None
        }
        mirrored = {
            str(item.get("name") or ""): int(item.get("size_bytes") or 0)
            for item in manifest.get("artifacts", [])
        }
        return bool(upstream) and upstream == mirrored

    async def _download_asset(self, asset: dict[str, Any], destination: Path) -> tuple[int, str]:
        api_url = str(asset.get("url") or "")
        browser_url = str(asset.get("browser_download_url") or "")
        url = api_url or browser_url
        if not url:
            raise APIError("DISTRIBUTION_ASSET_INVALID", "Asset da release sem URL de download.", 424)

        size = 0
        digest = hashlib.sha256()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300), follow_redirects=True) as client:
                async with client.stream("GET", url, headers=self._source_headers(binary=bool(api_url))) as response:
                    if response.status_code >= 400:
                        raise APIError(
                            "DISTRIBUTION_ASSET_DOWNLOAD_FAILED",
                            "Não foi possível baixar um dos aplicativos da release.",
                            424,
                            {"name": asset.get("name"), "status_code": response.status_code},
                        )
                    with destination.open("wb") as handle:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
        except httpx.HTTPError as exc:
            raise APIError(
                "DISTRIBUTION_ASSET_DOWNLOAD_FAILED",
                "Falha de rede ao baixar aplicativo da release.",
                424,
                {"name": asset.get("name")},
            ) from exc
        return size, digest.hexdigest()

    async def _upload_file(self, path: Path, key: str, content_type: str | None) -> None:
        extra = {"ContentType": content_type or "application/octet-stream"}
        try:
            await asyncio.to_thread(self.s3.upload_file, str(path), self.bucket, key, ExtraArgs=extra)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise APIError(
                "DISTRIBUTION_STORAGE_UNAVAILABLE",
                "Falha ao armazenar aplicativo no bucket interno.",
                424,
                {"key": key, "error": str(exc)},
            ) from exc

    async def _write_manifest(self, manifest: dict[str, Any]) -> None:
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        release = str(manifest.get("release") or "unknown").replace("/", "-")
        archive_key = f"distribution/releases/{release}/manifest.json"
        for key in (archive_key, self.latest_key):
            try:
                await asyncio.to_thread(
                    self.s3.put_object,
                    Bucket=self.bucket,
                    Key=key,
                    Body=encoded,
                    ContentType="application/json",
                    CacheControl="no-cache",
                )
            except (BotoCoreError, ClientError, OSError) as exc:
                raise APIError("DISTRIBUTION_STORAGE_UNAVAILABLE", "Falha ao gravar catálogo interno.", 424) from exc

    async def sync_latest_release(self) -> dict[str, Any]:
        await self.ensure_bucket()
        release = await self.fetch_latest_release()
        current = await self.read_latest_manifest(required=False)
        if self._manifest_matches_release(current, release):
            return {
                "changed": False,
                "release": release.get("tag_name"),
                "artifacts": len(current.get("artifacts", [])) if current else 0,
            }

        tag = str(release.get("tag_name") or "release-unknown").replace("/", "-")
        artifacts: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="scheduler-pro-distribution-") as tmp:
            tmpdir = Path(tmp)
            for asset in release.get("assets", []):
                name = str(asset.get("name") or "")
                mapped = self._asset_target(name)
                if mapped is None:
                    continue
                target, artifact_type = mapped
                safe_name = name.replace("/", "_")
                local_path = tmpdir / safe_name
                size, sha256 = await self._download_asset(asset, local_path)
                object_key = f"distribution/releases/{tag}/{target}/{safe_name}"
                await self._upload_file(
                    local_path,
                    object_key,
                    str(asset.get("content_type") or "application/octet-stream"),
                )
                artifact_id = hashlib.sha256(f"{tag}:{name}".encode()).hexdigest()[:24]
                artifacts.append(
                    {
                        "id": artifact_id,
                        "target": target,
                        "artifact_type": artifact_type,
                        "name": name,
                        "object_key": object_key,
                        "size_bytes": size,
                        "sha256": sha256,
                        "created_at": asset.get("created_at"),
                        "metadata": {
                            "universal": True,
                            "release": release.get("tag_name"),
                            "content_type": asset.get("content_type"),
                            "source_asset_id": asset.get("id"),
                        },
                    }
                )

        if not artifacts:
            raise APIError("DISTRIBUTION_ASSETS_MISSING", "A release não contém binários universais reconhecidos.", 424)

        manifest = {
            "universal": True,
            "source": "internal_bucket",
            "release": release.get("tag_name"),
            "published_at": release.get("published_at"),
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts,
        }
        await self._write_manifest(manifest)
        return {"changed": True, "release": release.get("tag_name"), "artifacts": len(artifacts)}

    async def get_artifact_object(self, artifact_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = await self.read_latest_manifest(required=True)
        assert manifest is not None
        artifact = next(
            (item for item in manifest.get("artifacts", []) if str(item.get("id")) == artifact_id),
            None,
        )
        if artifact is None:
            raise APIError("DISTRIBUTION_ARTIFACT_NOT_FOUND", "Aplicativo não encontrado no catálogo atual.", 404)
        key = str(artifact.get("object_key") or "")
        if not key.startswith("distribution/releases/"):
            raise APIError("DISTRIBUTION_ARTIFACT_INVALID", "Referência interna de aplicativo inválida.", 500)
        try:
            result = await asyncio.to_thread(self.s3.get_object, Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise APIError("DISTRIBUTION_ARTIFACT_NOT_FOUND", "Arquivo do aplicativo não encontrado no storage.", 404) from exc
        return artifact, result

    @staticmethod
    def iter_body(body: Any) -> Iterator[bytes]:
        try:
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

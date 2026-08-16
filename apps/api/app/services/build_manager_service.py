from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.db.models_platform import BuildArtifact, BuildJob, BuildLog, BuildProfile, BuildRequest, Tenant, TenantBrandingProfile
from app.services.github_actions_service import GitHubActionsService

WORKFLOW_FILE_BY_TARGET = {
    "web": "distribution-artifacts.yml",
    "pwa": "distribution-artifacts.yml",
    "desktop": "desktop-artifacts.yml",
    "admin-desktop": "desktop-artifacts.yml",
    "android": "mobile-artifacts.yml",
    "ios": "mobile-artifacts.yml",
    "admin-android": "mobile-artifacts.yml",
    "admin-ios": "mobile-artifacts.yml",
}


@dataclass(slots=True)
class BuildRequestInput:
    tenant: str
    target: str
    profile: str | None = None
    requested_by: str | None = None
    source_ref: str = "main"
    source_sha: str | None = None
    payload: dict[str, object] | None = None


class BuildManagerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.github = GitHubActionsService()

    async def list_profiles(self, tenant: str | None = None) -> list[dict[str, object]]:
        stmt = select(BuildProfile).order_by(desc(BuildProfile.created_at))
        if tenant:
            stmt = stmt.where(BuildProfile.tenant_id == tenant)
        profiles = (await self.session.execute(stmt.limit(200))).scalars().all()
        return [self._profile_dict(profile) for profile in profiles]

    @staticmethod
    def _uuid_or_none(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return str(UUID(value))
        except ValueError:
            return None

    async def _profile(self, payload: BuildRequestInput, target: str) -> BuildProfile | None:
        if payload.profile:
            profile = await self.session.get(BuildProfile, payload.profile)
            if profile is None or str(profile.tenant_id) != payload.tenant:
                raise APIError("BUILD_PROFILE_NOT_FOUND", "Perfil de build não encontrado para o tenant.", 404)
            return profile
        return (
            await self.session.execute(
                select(BuildProfile)
                .where(BuildProfile.tenant_id == payload.tenant, BuildProfile.target == target)
                .order_by(desc(BuildProfile.created_at))
                .limit(1)
            )
        ).scalar_one_or_none()

    async def create_build_request(self, payload: BuildRequestInput) -> dict[str, object]:
        target = payload.target.lower()
        workflow_file = WORKFLOW_FILE_BY_TARGET.get(target)
        if workflow_file is None:
            raise APIError("BUILD_TARGET_INVALID", "Alvo de build inválido.", 422, {"target": target})
        tenant = await self.session.get(Tenant, payload.tenant)
        if tenant is None:
            raise APIError("TENANT_NOT_FOUND", "Tenant não encontrado para o build.", 404)
        profile = await self._profile(payload, target)
        correlation_id = f"build_{uuid4().hex}"
        request_payload: dict[str, object] = dict(payload.payload or {})
        if payload.requested_by and self._uuid_or_none(payload.requested_by) is None:
            request_payload["requested_by_label"] = payload.requested_by
        request = BuildRequest(
            tenant_id=payload.tenant,
            build_profile_id=profile.id if profile else None,
            target=target,
            status="QUEUED",
            requested_by=self._uuid_or_none(payload.requested_by),
            request_payload=request_payload,
            correlation_id=correlation_id,
        )
        self.session.add(request)
        await self.session.flush()
        job = BuildJob(
            build_request_id=request.id,
            tenant_id=payload.tenant,
            target=target,
            status="QUEUED",
            workflow_name=workflow_file,
            source_ref=payload.source_ref,
            source_sha=payload.source_sha,
            runner_label=self._runner_label(target),
            artifact_manifest=self._expected_artifacts(target, request.id),
        )
        self.session.add(job)
        await self.session.flush()
        self.session.add(BuildLog(build_job_id=job.id, sequence=1, level="INFO", message="Build request persisted.", context={"workflow": workflow_file, "target": target, "correlation_id": correlation_id}))
        await self.session.commit()

        try:
            inputs = await self._workflow_inputs(tenant, profile, target, correlation_id)
            dispatch = await self.github.dispatch(workflow_file, ref=payload.source_ref or "main", inputs=inputs)
        except APIError as exc:
            job.status = "WAITING_CONFIGURATION" if exc.code == "GITHUB_ACTIONS_NOT_CONFIGURED" else "FAILED"
            job.error = exc.message
            request.status = job.status
            self.session.add(BuildLog(build_job_id=job.id, sequence=2, level="WARNING" if job.status == "WAITING_CONFIGURATION" else "ERROR", message=exc.message, context={"code": exc.code, "details": exc.details}))
            await self.session.commit()
            return await self.get_job(str(job.id))

        job.status = "DISPATCHED"
        request.status = "DISPATCHED"
        job.started_at = datetime.now(UTC)
        self.session.add(BuildLog(build_job_id=job.id, sequence=2, level="INFO", message="GitHub Actions workflow dispatched.", context=dispatch))
        await self.session.commit()
        return await self.get_job(str(job.id))

    async def _workflow_inputs(self, tenant: Tenant, profile: BuildProfile | None, target: str, correlation_id: str) -> dict[str, str]:
        config = profile.config if profile and isinstance(profile.config, dict) else {}
        web_url = str(config.get("web_url") or (str(profile.api_url).removesuffix("/api/v1") if profile else f"https://{tenant.slug}.scheduler.argws.com.br"))
        public_name = tenant.name
        branding = (
            await self.session.execute(select(TenantBrandingProfile).where(TenantBrandingProfile.tenant_id == tenant.id))
        ).scalar_one_or_none()
        if branding and branding.public_name:
            public_name = branding.public_name
        if target in {"desktop", "admin-desktop"}:
            return {
                "distribution_slug": tenant.slug,
                "client_web_url": web_url,
                "admin_web_url": "https://admin.scheduler.argws.com.br",
                "client_product_name": public_name,
                "correlation_id": correlation_id,
            }
        if target in {"android", "ios", "admin-android", "admin-ios"}:
            return {
                "build_profile": str(profile.id) if profile else tenant.slug,
                "target": target,
                "correlation_id": correlation_id,
            }
        return {"artifact_suffix": tenant.slug, "correlation_id": correlation_id}

    async def refresh_job(self, job_id: str) -> dict[str, object]:
        job = (await self.session.execute(select(BuildJob).where(BuildJob.id == job_id))).scalar_one()
        request = await self.session.get(BuildRequest, job.build_request_id)
        if not job.workflow_name or request is None:
            return await self._job_dict(job)
        runs = await self.github.latest_runs(job.workflow_name, branch=job.source_ref or "main", limit=20)
        match = next((run for run in runs if request.correlation_id in str(run.get("display_title") or run.get("name") or "")), None)
        if match:
            job.workflow_run_id = str(match.get("id"))
            status = str(match.get("status") or "").lower()
            conclusion = str(match.get("conclusion") or "").lower()
            if status == "completed":
                job.status = "COMPLETED" if conclusion == "success" else "FAILED"
                request.status = job.status
                job.finished_at = datetime.now(UTC)
                if conclusion and conclusion != "success":
                    job.error = f"GitHub Actions: {conclusion}"
            else:
                job.status = "BUILDING"
                request.status = "BUILDING"
            sequence = await self._next_log_sequence(str(job.id))
            self.session.add(BuildLog(build_job_id=job.id, sequence=sequence, level="INFO", message=f"Workflow status synchronized: {job.status}", context={"workflow_run_id": job.workflow_run_id, "html_url": match.get("html_url")}))
            await self.session.commit()
        return await self._job_dict(job)

    async def list_jobs(self, tenant: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        stmt = select(BuildJob).order_by(desc(BuildJob.created_at)).limit(min(limit, 200))
        if tenant:
            stmt = stmt.where(BuildJob.tenant_id == tenant)
        jobs = (await self.session.execute(stmt)).scalars().all()
        return [await self._job_dict(job) for job in jobs]

    async def get_job(self, job_id: str) -> dict[str, object]:
        job = (await self.session.execute(select(BuildJob).where(BuildJob.id == job_id))).scalar_one()
        return await self._job_dict(job)

    async def register_artifact(self, job_id: str, artifact_type: str, name: str, download_url: str | None = None, checksum: str | None = None, size_bytes: int = 0, metadata: dict[str, object] | None = None) -> dict[str, object]:
        job = (await self.session.execute(select(BuildJob).where(BuildJob.id == job_id))).scalar_one()
        artifact = BuildArtifact(build_job_id=job.id, tenant_id=job.tenant_id, target=job.target, artifact_type=artifact_type, name=name, download_url=download_url, checksum_sha256=checksum, size_bytes=size_bytes, artifact_metadata=metadata or {})
        self.session.add(artifact); await self.session.flush(); self.session.add(BuildLog(build_job_id=job.id, sequence=await self._next_log_sequence(str(job.id)), level="INFO", message=f"Artifact registered: {name}", context={"artifact_type": artifact_type})); await self.session.commit(); return self._artifact_dict(artifact)

    async def _job_dict(self, job: BuildJob) -> dict[str, object]:
        logs=(await self.session.execute(select(BuildLog).where(BuildLog.build_job_id==job.id).order_by(BuildLog.sequence))).scalars().all(); artifacts=(await self.session.execute(select(BuildArtifact).where(BuildArtifact.build_job_id==job.id).order_by(BuildArtifact.created_at))).scalars().all()
        return {"id":job.id,"build_request_id":job.build_request_id,"tenant":job.tenant_id,"target":job.target,"status":job.status,"workflow_name":job.workflow_name,"workflow_run_id":job.workflow_run_id,"source_ref":job.source_ref,"source_sha":job.source_sha,"runner_label":job.runner_label,"artifact_manifest":job.artifact_manifest,"error":job.error,"logs":[self._log_dict(log) for log in logs],"artifacts":[self._artifact_dict(a) for a in artifacts],"created_at":job.created_at.isoformat() if job.created_at else None}

    async def _next_log_sequence(self, job_id: str) -> int:
        logs=(await self.session.execute(select(BuildLog).where(BuildLog.build_job_id==job_id))).scalars().all();return len(logs)+1

    def _profile_dict(self,p:BuildProfile)->dict[str,object]:return {"id":p.id,"tenant":p.tenant_id,"branding_profile_id":p.branding_profile_id,"name":p.name,"target":p.target,"bundle_identifier":p.bundle_identifier,"package_name":p.package_name,"api_url":p.api_url,"features":p.features,"config":p.config}
    def _log_dict(self,l:BuildLog)->dict[str,object]:return {"sequence":l.sequence,"level":l.level,"message":l.message,"context":l.context,"created_at":l.created_at.isoformat() if l.created_at else None}
    def _artifact_dict(self,a:BuildArtifact)->dict[str,object]:return {"id":a.id,"target":a.target,"artifact_type":a.artifact_type,"name":a.name,"download_url":a.download_url,"checksum_sha256":a.checksum_sha256,"size_bytes":a.size_bytes,"metadata":a.artifact_metadata}
    def _runner_label(self,target:str)->str:return "macos-latest" if target in {"ios","admin-ios"} else "matrix" if target in {"desktop","admin-desktop"} else "ubuntu-latest"
    def _expected_artifacts(self,target:str,request_id:str)->dict[str,object]:
        suffix=str(request_id)[:8]
        if target in {"desktop","admin-desktop"}:return {"expected":[f"scheduler-pro-{target}-windows-{suffix}",f"scheduler-pro-{target}-linux-{suffix}",f"scheduler-pro-{target}-macos-{suffix}"]}
        if target in {"android","admin-android"}:return {"expected":[f"scheduler-pro-{target}-debug-installable-{suffix}.apk"]}
        if target in {"ios","admin-ios"}:return {"expected":[f"scheduler-pro-{target}-unsigned-{suffix}.ipa"]}
        return {"expected":[f"scheduler-pro-web-{suffix}.tar.gz",f"scheduler-pro-admin-{suffix}.tar.gz"]}

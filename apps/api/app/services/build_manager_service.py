from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_platform import BuildArtifact, BuildJob, BuildLog, BuildProfile, BuildRequest


WORKFLOW_BY_TARGET = {
    "web": "Distribution Artifacts",
    "pwa": "Distribution Artifacts",
    "desktop": "Desktop Artifacts",
    "android": "Mobile Artifacts",
    "ios": "Mobile Artifacts",
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

    async def list_profiles(self, tenant: str | None = None) -> list[dict[str, object]]:
        stmt = select(BuildProfile).order_by(desc(BuildProfile.created_at))
        if tenant:
            stmt = stmt.where(BuildProfile.tenant_id == tenant)
        profiles = (await self.session.execute(stmt.limit(100))).scalars().all()
        return [self._profile_dict(profile) for profile in profiles]

    async def create_build_request(self, payload: BuildRequestInput) -> dict[str, object]:
        target = payload.target.lower()
        workflow_name = WORKFLOW_BY_TARGET.get(target, "Distribution Artifacts")
        correlation_id = f"build_{uuid4().hex}"
        request = BuildRequest(
            tenant_id=payload.tenant,
            build_profile_id=payload.profile,
            target=target,
            status="QUEUED",
            requested_by=payload.requested_by,
            request_payload=payload.payload or {},
            correlation_id=correlation_id,
        )
        self.session.add(request)
        await self.session.flush()
        job = BuildJob(
            build_request_id=request.id,
            tenant_id=payload.tenant,
            target=target,
            status="QUEUED",
            workflow_name=workflow_name,
            source_ref=payload.source_ref,
            source_sha=payload.source_sha,
            runner_label=self._runner_label(target),
            artifact_manifest=self._expected_artifacts(target, request.id),
        )
        self.session.add(job)
        await self.session.flush()
        self.session.add(
            BuildLog(
                build_job_id=job.id,
                sequence=1,
                level="INFO",
                message="Build request queued. Dispatch the matching GitHub Actions workflow or let release pipeline process it.",
                context={"workflow_name": workflow_name, "target": target, "source_ref": payload.source_ref},
            )
        )
        await self.session.commit()
        return await self.get_job(job.id)

    async def list_jobs(self, tenant: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        stmt = select(BuildJob).order_by(desc(BuildJob.created_at)).limit(min(limit, 200))
        if tenant:
            stmt = stmt.where(BuildJob.tenant_id == tenant)
        jobs = (await self.session.execute(stmt)).scalars().all()
        return [await self._job_dict(job) for job in jobs]

    async def get_job(self, job_id: str) -> dict[str, object]:
        job = (await self.session.execute(select(BuildJob).where(BuildJob.id == job_id))).scalar_one()
        return await self._job_dict(job)

    async def register_artifact(
        self,
        job_id: str,
        artifact_type: str,
        name: str,
        download_url: str | None = None,
        checksum: str | None = None,
        size_bytes: int = 0,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        job = (await self.session.execute(select(BuildJob).where(BuildJob.id == job_id))).scalar_one()
        artifact = BuildArtifact(
            build_job_id=job.id,
            tenant_id=job.tenant_id,
            target=job.target,
            artifact_type=artifact_type,
            name=name,
            download_url=download_url,
            checksum_sha256=checksum,
            size_bytes=size_bytes,
            artifact_metadata=metadata or {},
        )
        self.session.add(artifact)
        await self.session.flush()
        self.session.add(BuildLog(build_job_id=job.id, sequence=await self._next_log_sequence(job.id), level="INFO", message=f"Artifact registered: {name}", context={"artifact_type": artifact_type}))
        await self.session.commit()
        return self._artifact_dict(artifact)

    async def _job_dict(self, job: BuildJob) -> dict[str, object]:
        logs = (await self.session.execute(select(BuildLog).where(BuildLog.build_job_id == job.id).order_by(BuildLog.sequence))).scalars().all()
        artifacts = (await self.session.execute(select(BuildArtifact).where(BuildArtifact.build_job_id == job.id).order_by(BuildArtifact.created_at))).scalars().all()
        return {
            "id": job.id,
            "build_request_id": job.build_request_id,
            "tenant": job.tenant_id,
            "target": job.target,
            "status": job.status,
            "workflow_name": job.workflow_name,
            "workflow_run_id": job.workflow_run_id,
            "source_ref": job.source_ref,
            "source_sha": job.source_sha,
            "runner_label": job.runner_label,
            "artifact_manifest": job.artifact_manifest,
            "error": job.error,
            "logs": [self._log_dict(log) for log in logs],
            "artifacts": [self._artifact_dict(artifact) for artifact in artifacts],
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }

    async def _next_log_sequence(self, job_id: str) -> int:
        logs = (await self.session.execute(select(BuildLog).where(BuildLog.build_job_id == job_id))).scalars().all()
        return len(logs) + 1

    def _profile_dict(self, profile: BuildProfile) -> dict[str, object]:
        return {
            "id": profile.id,
            "tenant": profile.tenant_id,
            "branding_profile_id": profile.branding_profile_id,
            "name": profile.name,
            "target": profile.target,
            "bundle_identifier": profile.bundle_identifier,
            "package_name": profile.package_name,
            "api_url": profile.api_url,
            "features": profile.features,
            "config": profile.config,
        }

    def _log_dict(self, log: BuildLog) -> dict[str, object]:
        return {"sequence": log.sequence, "level": log.level, "message": log.message, "context": log.context, "created_at": log.created_at.isoformat() if log.created_at else None}

    def _artifact_dict(self, artifact: BuildArtifact) -> dict[str, object]:
        return {
            "id": artifact.id,
            "target": artifact.target,
            "artifact_type": artifact.artifact_type,
            "name": artifact.name,
            "download_url": artifact.download_url,
            "checksum_sha256": artifact.checksum_sha256,
            "size_bytes": artifact.size_bytes,
            "metadata": artifact.artifact_metadata,
        }

    def _runner_label(self, target: str) -> str:
        return {"ios": "macos-latest", "desktop": "matrix", "android": "ubuntu-latest"}.get(target, "ubuntu-latest")

    def _expected_artifacts(self, target: str, request_id: str) -> dict[str, object]:
        suffix = str(request_id)[:8]
        if target == "desktop":
            return {"expected": [f"scheduler-pro-desktop-windows-{suffix}", f"scheduler-pro-desktop-linux-{suffix}", f"scheduler-pro-desktop-macos-{suffix}"]}
        if target in {"android", "ios"}:
            return {"expected": [f"scheduler-pro-mobile-{target}-{suffix}"]}
        return {"expected": [f"scheduler-pro-web-{suffix}.tar.gz", f"scheduler-pro-admin-{suffix}.tar.gz", f"scheduler-pro-deploy-{suffix}.tar.gz"]}

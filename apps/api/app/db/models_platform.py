from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TenantStatus
from app.db.base import PlatformBase


class Tenant(PlatformBase):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TenantStatus.pending.value
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Bahia"
    )
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    database: Mapped["TenantDatabase"] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    storage: Mapped["TenantStorage"] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantDatabase(PlatformBase):
    __tablename__ = "tenant_databases"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    database_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    database_user: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_ref: Mapped[str] = mapped_column(Text, nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tenant: Mapped[Tenant] = relationship(back_populates="database")


class TenantStorage(PlatformBase):
    __tablename__ = "tenant_storage"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    bucket: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    tenant: Mapped[Tenant] = relationship(back_populates="storage")


class Domain(PlatformBase):
    __tablename__ = "domains"
    __table_args__ = (UniqueConstraint("hostname", name="uq_domains_hostname"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ProvisioningJob(PlatformBase):
    __tablename__ = "provisioning_jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProvisioningStep(PlatformBase):
    __tablename__ = "provisioning_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "name", name="uq_provisioning_job_step"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("provisioning_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text)


class PlatformUser(PlatformBase):
    __tablename__ = "platform_users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    email: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FeatureFlag(PlatformBase):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class TenantBrandingProfile(PlatformBase):
    __tablename__ = "tenant_branding_profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    app_name: Mapped[str] = mapped_column(String(160), nullable=False)
    public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    slogan: Mapped[str | None] = mapped_column(String(220))
    logo_url: Mapped[str | None] = mapped_column(Text)
    icon_url: Mapped[str | None] = mapped_column(Text)
    favicon_url: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#0f172a"
    )
    secondary_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#22d3ee"
    )
    accent_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#38bdf8"
    )
    background_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#020617"
    )
    text_color: Mapped[str] = mapped_column(
        String(20), nullable=False, default="#f8fafc"
    )
    font_family: Mapped[str] = mapped_column(
        String(120), nullable=False, default="Inter, ui-sans-serif, system-ui"
    )
    border_radius: Mapped[str] = mapped_column(String(20), nullable=False, default="1rem")
    theme_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    locale: Mapped[str] = mapped_column(String(20), nullable=False, default="pt-BR")
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Bahia"
    )
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TenantBrandingAsset(PlatformBase):
    __tablename__ = "tenant_branding_assets"
    __table_args__ = (
        UniqueConstraint(
            "branding_profile_id", "asset_type", "storage_key", name="uq_branding_asset"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branding_profile_id: Mapped[str] = mapped_column(
        ForeignKey("tenant_branding_profiles.id", ondelete="CASCADE"), nullable=False
    )
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_url: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildProfile(PlatformBase):
    __tablename__ = "build_profiles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "target", "name", name="uq_build_profile_tenant_target_name"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branding_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("tenant_branding_profiles.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    target: Mapped[str] = mapped_column(String(40), nullable=False)
    bundle_identifier: Mapped[str | None] = mapped_column(String(200))
    package_name: Mapped[str | None] = mapped_column(String(200))
    api_url: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildRequest(PlatformBase):
    __tablename__ = "build_requests"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    build_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("build_profiles.id", ondelete="SET NULL"), index=True
    )
    target: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    requested_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildJob(PlatformBase):
    __tablename__ = "build_jobs"
    __table_args__ = (
        UniqueConstraint("build_request_id", "target", name="uq_build_job_request_target"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    build_request_id: Mapped[str] = mapped_column(
        ForeignKey("build_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    workflow_name: Mapped[str | None] = mapped_column(String(120))
    workflow_run_id: Mapped[str | None] = mapped_column(String(120))
    source_ref: Mapped[str | None] = mapped_column(String(160))
    source_sha: Mapped[str | None] = mapped_column(String(80))
    runner_label: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    artifact_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildLog(PlatformBase):
    __tablename__ = "build_logs"
    __table_args__ = (
        UniqueConstraint("build_job_id", "sequence", name="uq_build_log_job_sequence"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    build_job_id: Mapped[str] = mapped_column(
        ForeignKey("build_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildArtifact(PlatformBase):
    __tablename__ = "build_artifacts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    build_job_id: Mapped[str] = mapped_column(
        ForeignKey("build_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target: Mapped[str] = mapped_column(String(40), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text)
    download_url: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    artifact_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildCredential(PlatformBase):
    __tablename__ = "build_credentials"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "target",
            "credential_type",
            name="uq_build_credential_tenant_target_type",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target: Mapped[str] = mapped_column(String(40), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(80), nullable=False)
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    credential_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TenantStatus
from app.db.base import PlatformBase


class Tenant(PlatformBase):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TenantStatus.pending.value)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Bahia")
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    database: Mapped["TenantDatabase"] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    storage: Mapped["TenantStorage"] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantDatabase(PlatformBase):
    __tablename__ = "tenant_databases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    database_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    database_user: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_ref: Mapped[str] = mapped_column(Text, nullable=False)
    tenant: Mapped[Tenant] = relationship(back_populates="database")


class TenantStorage(PlatformBase):
    __tablename__ = "tenant_storage"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    bucket: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    tenant: Mapped[Tenant] = relationship(back_populates="storage")


class Domain(PlatformBase):
    __tablename__ = "domains"
    __table_args__ = (UniqueConstraint("hostname", name="uq_domains_hostname"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ProvisioningJob(PlatformBase):
    __tablename__ = "provisioning_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    correlation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProvisioningStep(PlatformBase):
    __tablename__ = "provisioning_steps"
    __table_args__ = (UniqueConstraint("job_id", "name", name="uq_provisioning_job_step"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("provisioning_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text)


class PlatformUser(PlatformBase):
    __tablename__ = "platform_users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FeatureFlag(PlatformBase):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

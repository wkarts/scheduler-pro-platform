from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import quote_plus
from uuid import uuid4

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scheduler Pro"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me"
    public_platform_domain: str = "localhost"
    admin_platform_domains: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["admin.localhost", "localhost"])
    tenant_default_domain_root: str | None = None
    public_base_url: str | None = None

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "platform"
    postgres_user: str = "scheduler"
    postgres_password: str = "scheduler_dev_password"
    postgres_admin_user: str = "scheduler"
    postgres_admin_password: str = "scheduler_dev_password"

    platform_admin_email: str | None = None
    platform_admin_password: str | None = None

    dev_tenant_database: str = "tenant_dev"
    dev_tenant_database_user: str = "tenant_dev_user"
    dev_tenant_database_password: str = "tenant_dev_password"
    dev_tenant_database_password_ref: str = "secret://env/TENANT_DEV_DATABASE_PASSWORD"
    dev_tenant_slug: str = "dev"
    dev_tenant_name: str = "Scheduler Pro Development"
    dev_tenant_bucket: str = "tenant-dev"
    dev_tenant_admin_email: str = "admin@tenant.example"
    dev_tenant_admin_password: str = "ChangeMe-Tenant-2026!"
    dev_platform_admin_email: str = "admin@platform.example"
    dev_platform_admin_password: str = "ChangeMe-Platform-2026!"

    access_token_minutes: int = 15
    refresh_token_days: int = 30
    max_login_attempts: int = 5
    login_lock_minutes: int = 15
    tenant_engine_cache_max: int = 64
    tenant_engine_cache_ttl_seconds: int = 900
    trusted_proxy_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["127.0.0.1", "::1"])

    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://scheduler:scheduler@localhost:5672//"
    celery_broker_url: str = "amqp://scheduler:scheduler@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "scheduler"
    s3_secret_key: str = "scheduler_dev_secret"
    s3_region: str = "us-east-1"

    cloudflare_api_base_url: str = "https://api.cloudflare.com/client/v4"
    cloudflare_api_token: str | None = None
    cloudflare_zone_id: str | None = None
    cloudflare_dry_run: bool = True
    cloudflare_custom_hostname_origin: str | None = None
    cloudflare_temporary_record_type: str = "CNAME"
    cloudflare_temporary_record_target: str | None = None

    whatsapp_provider: str = "evolution"
    evolution_api_url: str | None = None
    evolution_api_token: str | None = None
    evolution_instance_name: str = "scheduler-pro"

    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174", "http://localhost:1420"])

    @field_validator("cors_allowed_origins", "trusted_proxy_hosts", "admin_platform_domains", mode="before")
    @classmethod
    def split_csv_values(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env != "development":
            if len(self.app_secret_key) < 64 or self.app_secret_key.startswith("change-me"):
                raise ValueError("APP_SECRET_KEY must contain at least 64 non-placeholder characters")
        return self

    @property
    def effective_platform_admin_email(self) -> str:
        return (self.platform_admin_email or self.dev_platform_admin_email).lower()

    @property
    def effective_platform_admin_password(self) -> str:
        return self.platform_admin_password or self.dev_platform_admin_password

    @property
    def tenant_domain_root(self) -> str:
        return (self.tenant_default_domain_root or self.public_platform_domain).strip().lower()

    @property
    def tenant_domain_target(self) -> str:
        return (self.cloudflare_temporary_record_target or self.public_platform_domain).strip()

    @property
    def platform_public_url(self) -> str:
        if self.public_base_url:
            return self.public_base_url.rstrip("/")
        if self.public_platform_domain == "localhost":
            return "http://localhost:5173"
        return f"https://{self.public_platform_domain}"

    @staticmethod
    def _database_url(driver: str, user: str, password: str, host: str, port: int, database: str) -> str:
        return f"postgresql+{driver}://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}"

    @property
    def platform_database_url(self) -> str:
        return self._database_url("asyncpg", self.postgres_user, self.postgres_password, self.postgres_host, self.postgres_port, self.postgres_db)

    @property
    def platform_database_url_sync(self) -> str:
        return self._database_url("psycopg", self.postgres_user, self.postgres_password, self.postgres_host, self.postgres_port, self.postgres_db)

    def tenant_database_url(self, database: str, user: str, password: str) -> str:
        return self._database_url("asyncpg", user, password, self.postgres_host, self.postgres_port, database)

    def tenant_database_url_sync(self, database: str, user: str, password: str) -> str:
        return self._database_url("psycopg", user, password, self.postgres_host, self.postgres_port, database)

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

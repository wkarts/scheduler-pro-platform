from functools import lru_cache
from uuid import uuid4

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Scheduler Pro"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me"
    public_platform_domain: str = "localhost"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "platform"
    postgres_user: str = "scheduler"
    postgres_password: str = "scheduler_dev_password"
    postgres_admin_user: str = "postgres"
    postgres_admin_password: str = "postgres_dev_password"

    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://scheduler:scheduler@localhost:5672//"
    celery_broker_url: str = "amqp://scheduler:scheduler@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "scheduler"
    s3_secret_key: str = "scheduler_dev_secret"
    s3_region: str = "us-east-1"

    cloudflare_api_token: str | None = None
    cloudflare_zone_id: str | None = None
    whatsapp_provider: str = "evolution"
    evolution_api_url: str | None = None
    evolution_api_token: str | None = None

    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174", "http://localhost:1420"])

    @property
    def platform_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    def tenant_database_url(self, database: str, user: str, password: str) -> str:
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{database}"

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

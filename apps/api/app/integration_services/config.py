"""Bounded, opt-out integration runtime; independent from browser authentication."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTEGRATION_", extra="ignore")

    api_enabled: bool = True
    webhooks_enabled: bool = True
    incoming_webhooks_enabled: bool = True
    inbox_max_bytes: int = Field(default=256 * 1024, ge=1024, le=1024 * 1024)
    inbox_max_payloads: int = Field(default=1000, ge=1, le=10000)
    inbox_max_inflight: int = Field(default=16, ge=1, le=128)
    max_inflight_requests: int = Field(default=32, ge=1, le=256)
    body_timeout_seconds: float = Field(default=15, ge=1, le=60)
    max_tokens: int = Field(default=50, ge=1, le=500)
    max_endpoints: int = Field(default=20, ge=1, le=100)
    max_request_bytes: int = Field(default=16 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    max_response_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=8 * 1024 * 1024)
    replay_hours: int = Field(default=24, ge=1, le=168)
    retention_days: int = Field(default=30, ge=7, le=90)
    max_pending_requests: int = Field(default=100, ge=1, le=1000)
    webhook_timeout_seconds: float = Field(default=10, ge=1, le=20)
    webhook_batch_size: int = Field(default=5, ge=1, le=20)
    webhook_max_attempts: int = Field(default=8, ge=1, le=12)


integration_settings = IntegrationSettings()

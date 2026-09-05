"""Independent API credentials, idempotency ledger and transactional webhook outbox."""

from pathlib import Path

from alembic import op

revision = "platform_0013_integrations"
down_revision = "platform_0012_login_surface"
branch_labels = None
depends_on = None

TABLES = {
    "tenants": "tenant",
    "domains": "domain",
    "provisioning_jobs": "provisioning",
    "build_jobs": "build",
    "global_content_templates": "template",
}


def upgrade() -> None:
    sql = Path(__file__).resolve().parents[2] / "shared" / "0013_integration_services.sql"
    op.execute(sql.read_text(encoding="utf-8"))
    op.execute(
        "alter table service_api_tokens add foreign key(owner_id) references platform_users(id) on delete cascade"
    )
    for table, event in TABLES.items():
        op.execute(
            f"create trigger service_webhook_changes after insert or update or delete on {table} "
            f"for each row execute function service_capture_webhook('{event}')"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"drop trigger if exists service_webhook_changes on {table}")
    op.execute("drop function if exists service_capture_webhook()")
    for table in (
        "service_integration_audit",
        "service_webhook_attempts",
        "service_webhook_deliveries",
        "service_webhook_events",
        "service_webhook_endpoints",
        "service_api_requests",
        "service_api_usage",
        "service_api_tokens",
        "service_integration_sweep",
    ):
        op.execute(f"drop table if exists {table}")

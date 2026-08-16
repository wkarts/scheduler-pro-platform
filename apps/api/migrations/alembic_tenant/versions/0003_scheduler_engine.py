from pathlib import Path

from alembic import op

revision = "tenant_0003_scheduler_engine"
down_revision = "tenant_0002"
branch_labels = None
depends_on = None

SQL_PATH = Path(__file__).resolve().parents[2] / "tenant" / "002_scheduler_engine.sql"


def upgrade() -> None:
    op.execute(SQL_PATH.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("drop table if exists whatsapp_integrations cascade")
    op.execute("drop table if exists notification_jobs cascade")
    op.execute("drop table if exists notification_templates cascade")
    op.execute("drop table if exists appointment_notes cascade")
    op.execute("drop table if exists appointment_status_history cascade")
    op.execute("drop table if exists blocked_periods cascade")
    op.execute("drop table if exists business_hours cascade")

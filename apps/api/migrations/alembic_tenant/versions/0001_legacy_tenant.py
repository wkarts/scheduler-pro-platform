from pathlib import Path

from app.db.migration_utils import execute_sql_file

revision = "tenant_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(Path(__file__).resolve().parents[2] / "tenant" / "001_tenant_init.sql")


def downgrade() -> None:
    # Legacy baseline is intentionally non-destructive.
    pass

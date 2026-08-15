from pathlib import Path

from app.db.migration_utils import execute_sql_file

revision = "platform_0003"
down_revision = "platform_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    execute_sql_file(Path(__file__).resolve().parents[2] / "platform" / "003_build_manager.sql")


def downgrade() -> None:
    # Preserves already-persisted build data.
    pass

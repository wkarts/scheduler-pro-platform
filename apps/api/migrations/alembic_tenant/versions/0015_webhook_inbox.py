"""Optional API expiration and authenticated, isolated incoming webhook inbox."""

from pathlib import Path
from alembic import op

revision = "tenant_0015_webhook_inbox"
down_revision = "tenant_0014_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql = Path(__file__).resolve().parents[2] / "shared" / "0014_webhook_inbox.sql"
    op.execute(sql.read_text(encoding="utf-8"))
    op.execute(
        "alter table service_webhook_receivers add foreign key(created_by) references users(id) on delete set null"
    )


def downgrade() -> None:
    op.execute("drop table service_webhook_inbox")
    op.execute("drop table service_webhook_receivers")
    # Older runtime cannot represent indefinite validity. Never accidentally reactivate it.
    op.execute(
        "update service_api_tokens set revoked_at=coalesce(revoked_at,now()), expires_at=now() where expires_at is null"
    )
    op.execute("alter table service_api_tokens alter column expires_at set not null")

from alembic import op

revision = "platform_0009"
down_revision = "platform_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table domains
        add column if not exists created_at timestamptz not null default now()
        """
    )
    op.execute(
        """
        create index if not exists ix_domains_created_at
        on domains(created_at asc)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists ix_domains_created_at")
    op.execute("alter table domains drop column if exists created_at")

from alembic import op

revision = "tenant_0005_password_recovery"
down_revision = "tenant_0004_product_complete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists password_reset_tokens (
          id uuid primary key default uuid_generate_v4(),
          user_id uuid not null references users(id) on delete cascade,
          token_hash varchar(64) not null unique,
          expires_at timestamptz not null,
          used_at timestamptz,
          created_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        create index if not exists ix_password_reset_tokens_user_active
        on password_reset_tokens(user_id, expires_at desc)
        where used_at is null
        """
    )
    op.execute(
        """
        create index if not exists ix_password_reset_tokens_expires
        on password_reset_tokens(expires_at)
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists password_reset_tokens cascade")

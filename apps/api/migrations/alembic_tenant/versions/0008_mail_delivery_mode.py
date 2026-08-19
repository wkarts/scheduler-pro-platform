from alembic import op

revision = "tenant_0008_mail_mode"
down_revision = "tenant_0007_smtp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "alter table tenant_smtp_settings "
        "add column if not exists delivery_mode varchar(16) not null default 'tenant'"
    )
    op.execute(
        "alter table tenant_smtp_settings drop constraint if exists ck_tenant_smtp_delivery_mode"
    )
    op.execute(
        "alter table tenant_smtp_settings add constraint ck_tenant_smtp_delivery_mode "
        "check (delivery_mode in ('tenant','platform'))"
    )


def downgrade() -> None:
    op.execute(
        "alter table tenant_smtp_settings drop constraint if exists ck_tenant_smtp_delivery_mode"
    )
    op.execute("alter table tenant_smtp_settings drop column if exists delivery_mode")

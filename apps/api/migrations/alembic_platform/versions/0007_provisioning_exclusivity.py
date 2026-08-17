from alembic import op

revision = "platform_0007"
down_revision = "platform_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table provisioning_jobs
        add column if not exists updated_at timestamptz not null default now()
        """
    )
    op.execute(
        """
        with ranked as (
          select id,
                 row_number() over (
                   partition by tenant_id
                   order by created_at desc, id desc
                 ) as row_number
          from provisioning_jobs
          where status in ('PENDING', 'PROVISIONING')
        )
        update provisioning_jobs as job
        set status='SUPERSEDED', updated_at=now()
        from ranked
        where job.id=ranked.id and ranked.row_number > 1
        """
    )
    op.execute(
        """
        create unique index if not exists uq_provisioning_jobs_active_tenant
        on provisioning_jobs(tenant_id)
        where status in ('PENDING', 'PROVISIONING')
        """
    )
    op.execute(
        """
        create index if not exists ix_provisioning_jobs_updated_at
        on provisioning_jobs(updated_at desc)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists ix_provisioning_jobs_updated_at")
    op.execute("drop index if exists uq_provisioning_jobs_active_tenant")
    op.execute("alter table provisioning_jobs drop column if exists updated_at")

"""Experience Contract v2 pages and assets.

Revision ID: tenant_0011_experience_v2
Revises: tenant_0010_phone_guard
"""

from alembic import op

revision = "tenant_0011_experience_v2"
down_revision = "tenant_0010_phone_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists tenant_public_pages (
            id uuid primary key default uuid_generate_v4(),
            surface varchar(16) not null unique,
            route varchar(120) not null,
            template_key varchar(160),
            draft_version_id uuid,
            published_version_id uuid,
            enabled boolean not null default true,
            theme jsonb not null default '{}'::jsonb,
            bindings jsonb not null default '{}'::jsonb,
            settings jsonb not null default '{}'::jsonb,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint ck_tenant_public_page_surface check(surface in ('LANDING','BOOKING'))
        )
        """
    )
    op.execute(
        """
        create table if not exists tenant_public_page_versions (
            id uuid primary key default uuid_generate_v4(),
            page_id uuid not null references tenant_public_pages(id) on delete cascade,
            version_number integer not null,
            html text not null,
            metadata jsonb not null default '{}'::jsonb,
            bindings_values jsonb not null default '{}'::jsonb,
            theme jsonb not null default '{}'::jsonb,
            label varchar(180),
            published boolean not null default false,
            created_by uuid,
            created_at timestamptz not null default now(),
            unique(page_id, version_number)
        )
        """
    )
    op.execute(
        "create index if not exists ix_tenant_public_page_versions_page_created "
        "on tenant_public_page_versions(page_id, created_at desc)"
    )
    op.execute(
        """
        create table if not exists tenant_template_assets (
            id uuid primary key default uuid_generate_v4(),
            template_key varchar(160) not null,
            logical_key varchar(500) not null,
            storage_key varchar(600) not null,
            public_url text not null,
            sha256 varchar(64) not null,
            content_type varchar(160),
            size_bytes bigint not null default 0,
            created_at timestamptz not null default now(),
            unique(template_key, logical_key)
        )
        """
    )
    op.execute(
        "create index if not exists ix_tenant_template_assets_template "
        "on tenant_template_assets(template_key, created_at desc)"
    )
    op.execute(
        """
        insert into tenant_settings(key,value,updated_at)
        values
          ('experience_editor_level','\"basic\"'::jsonb,now()),
          ('experience_theme_apply_console','false'::jsonb,now()),
          ('marketing_analytics','{}'::jsonb,now()),
          ('pwa_open_mode','\"AUTO\"'::jsonb,now())
        on conflict(key) do nothing
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists tenant_template_assets cascade")
    op.execute("drop table if exists tenant_public_page_versions cascade")
    op.execute("drop table if exists tenant_public_pages cascade")

from alembic import op

revision = "tenant_0009_booking_phone_2fa"
down_revision = "tenant_0008_open_booking"
branch_labels = None
depends_on = None


def _setting(key: str, json_value: str) -> None:
    escaped_key = key.replace("'", "''")
    escaped_value = json_value.replace("'", "''")
    op.execute(
        "insert into tenant_settings(key, value, updated_at) "
        f"values ('{escaped_key}', '{escaped_value}'::jsonb, now()) "
        "on conflict(key) do nothing"
    )


def upgrade() -> None:
    # 2FA das empresas é opt-in. O default false preserva todos os acessos atuais.
    op.execute(
        "alter table users add column if not exists "
        "two_factor_enabled boolean not null default false"
    )
    op.execute("alter table users add column if not exists two_factor_secret_ref text")
    op.execute("alter table users add column if not exists two_factor_confirmed_at timestamptz")
    op.execute("alter table users add column if not exists two_factor_updated_at timestamptz")
    op.execute(
        "alter table user_sessions add column if not exists "
        "second_factor_verified boolean not null default false"
    )
    op.execute(
        "alter table user_sessions add column if not exists second_factor_verified_at timestamptz"
    )

    # Telefone: preservamos o valor legado e introduzimos a representação canônica
    # separada. A base histórica não é normalizada cegamente nesta migration.
    op.execute("alter table customers add column if not exists phone_normalized varchar(32)")
    op.execute("alter table professionals add column if not exists phone_normalized varchar(32)")
    op.execute(
        "create index if not exists ix_customers_phone_normalized "
        "on customers(phone_normalized)"
    )
    op.execute(
        "create index if not exists ix_professionals_phone_normalized "
        "on professionals(phone_normalized)"
    )
    op.execute(
        """
        create table if not exists phone_normalization_review (
            id uuid primary key default uuid_generate_v4(),
            entity_type varchar(40) not null,
            entity_id uuid not null,
            original_value varchar(80),
            normalized_value varchar(32),
            status varchar(32) not null,
            conflict_entity_id uuid,
            details jsonb not null default '{}'::jsonb,
            created_at timestamptz not null default now(),
            resolved_at timestamptz,
            unique(entity_type, entity_id, normalized_value)
        )
        """
    )
    op.execute(
        "create index if not exists ix_phone_normalization_review_status "
        "on phone_normalization_review(status, created_at desc)"
    )

    # Serviço passa a poder ser realmente ausente. A FK é preservada e nenhum
    # registro existente é alterado. O ORM/queries serão ajustados para LEFT JOIN.
    op.execute("alter table appointments alter column service_id drop not null")

    # A constraint da 0008 representava capacidade fixa 1. Capacidade variável
    # precisa ser decidida sob lock transacional pelo motor de agenda. Removemos
    # somente a constraint atual e mantemos índices para a consulta de overlap.
    op.execute(
        "alter table appointments "
        "drop constraint if exists ex_appointments_professional_active_range"
    )
    op.execute(
        "create index if not exists ix_appointments_professional_interval "
        "on appointments(professional_id, starts_at, ends_at, status)"
    )

    # Editor: amplia metadados sem substituir o conteúdo JSON/versionamento atual.
    op.execute("alter table landing_pages add column if not exists template_key varchar(80)")
    op.execute("alter table landing_pages add column if not exists settings jsonb not null default '{}'::jsonb")
    op.execute("alter table landing_pages add column if not exists draft_version_id uuid")
    op.execute("alter table landing_page_versions add column if not exists label varchar(160)")
    op.execute("alter table landing_page_versions add column if not exists source_version_id uuid")
    op.execute(
        "create index if not exists ix_landing_page_versions_page_version "
        "on landing_page_versions(landing_page_id, version_number desc)"
    )

    # Compatibilidade: serviço era sempre obrigatório e e-mail era opcional por
    # padrão. Novos parâmetros começam reproduzindo exatamente isso.
    _setting("booking_service_mode", '"REQUIRED"')
    op.execute(
        """
        insert into tenant_settings(key, value, updated_at)
        select 'booking_email_mode',
               case
                 when coalesce((select value::text from tenant_settings where key='public_booking_require_email'), 'false')='true'
                   then '"REQUIRED"'::jsonb
                 else '"OPTIONAL"'::jsonb
               end,
               now()
        on conflict(key) do nothing
        """
    )
    _setting("default_appointment_duration_minutes", "60")
    _setting("allow_simultaneous_public_booking", "false")
    _setting("allow_simultaneous_internal_booking", "false")
    _setting("simultaneous_booking_capacity", "1")
    _setting("minimum_notice_minutes", "1440")

    # Parâmetros de localização/telefone. DDD fica vazio até a empresa defini-lo;
    # não presumimos 75 para todos os tenants.
    _setting("phone_default_country", '"BR"')
    _setting("phone_country_code", '"55"')
    _setting("phone_default_area_code", '""')
    _setting("phone_add_ninth_digit", "true")


def downgrade() -> None:
    op.execute("drop index if exists ix_landing_page_versions_page_version")
    op.execute("alter table landing_page_versions drop column if exists source_version_id")
    op.execute("alter table landing_page_versions drop column if exists label")
    op.execute("alter table landing_pages drop column if exists draft_version_id")
    op.execute("alter table landing_pages drop column if exists settings")
    op.execute("alter table landing_pages drop column if exists template_key")

    # Downgrade para capacidade fixa 1 somente é seguro se não houver overlaps.
    # A própria DDL falhará em vez de destruir dados caso existam agendamentos
    # simultâneos, tornando o risco explícito.
    op.execute(
        """
        alter table appointments
        add constraint ex_appointments_professional_active_range
        exclude using gist (
          professional_id with =,
          tstzrange(starts_at, ends_at, '[)') with &&
        )
        where (status in (
          'PENDING','AWAITING_CONFIRMATION','CONFIRMED','CHECKED_IN','IN_PROGRESS'
        ))
        """
    )
    op.execute(
        """
        do $$
        begin
          if exists(select 1 from appointments where service_id is null) then
            raise exception 'Não é possível tornar service_id obrigatório: existem agendamentos sem serviço.';
          end if;
        end $$
        """
    )
    op.execute("alter table appointments alter column service_id set not null")
    op.execute("drop table if exists phone_normalization_review")
    op.execute("alter table professionals drop column if exists phone_normalized")
    op.execute("alter table customers drop column if exists phone_normalized")
    op.execute("alter table user_sessions drop column if exists second_factor_verified_at")
    op.execute("alter table user_sessions drop column if exists second_factor_verified")
    op.execute("alter table users drop column if exists two_factor_updated_at")
    op.execute("alter table users drop column if exists two_factor_confirmed_at")
    op.execute("alter table users drop column if exists two_factor_secret_ref")
    op.execute("alter table users drop column if exists two_factor_enabled")
